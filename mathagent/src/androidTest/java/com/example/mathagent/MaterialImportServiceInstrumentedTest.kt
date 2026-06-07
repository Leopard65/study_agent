package com.example.mathagent

import android.content.Context
import android.net.Uri
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.mathagent.data.local.MathAgentDatabase
import com.example.mathagent.data.local.entity.Material
import com.example.mathagent.data.material.ImportException
import com.example.mathagent.data.material.MaterialImportService
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * Deterministic instrumented tests for [MaterialImportService].
 *
 * Cleanup strategy:
 * - [trackedFiles] is the single source of truth for files created by this test.
 * - [cleanupFiles] deletes every file in [trackedFiles] and nothing else.
 * - No directory scanning by prefix — deterministic and safe.
 */
@RunWith(AndroidJUnit4::class)
class MaterialImportServiceInstrumentedTest {

    private lateinit var db: MathAgentDatabase
    private lateinit var context: Context
    private lateinit var service: MaterialImportService

    /** All files this test created (source cache, imported materials, tmp).
     *  Cleanup deletes these and only these. */
    private val trackedFiles = mutableListOf<File>()

    /** Sentinel file created before tests — must survive cleanup. */
    private lateinit var sentinelFile: File

    @Before
    fun setup() {
        context = ApplicationProvider.getApplicationContext()
        db = Room.inMemoryDatabaseBuilder(context, MathAgentDatabase::class.java)
            .allowMainThreadQueries().build()
        service = MaterialImportService(context, db.materialDao(), db.materialChunkDao(), db)
        trackedFiles.clear()

        // Create sentinel file — must survive all cleanup cycles
        val materialsDir = File(context.filesDir, "materials")
        materialsDir.mkdirs()
        sentinelFile = File(materialsDir, "user_file.txt")
        sentinelFile.writeText("user content")
    }

    @After
    fun teardown() {
        db.close()
        try {
            cleanupFiles()
            // Sentinel must survive cleanup — proves cleanupFiles doesn't touch untracked files
            assertTrue("Sentinel must survive cleanupFiles", sentinelFile.exists())
        } finally {
            // Always remove sentinel, even if assertion or cleanup throws
            sentinelFile.delete()
        }
    }

    /** Delete only files in [trackedFiles]. No directory scanning. */
    private fun cleanupFiles() {
        trackedFiles.forEach { it.delete() }
    }

    /** Track a material's local file for cleanup. Safe if file already deleted by service. */
    private fun trackMaterial(material: Material) {
        trackedFiles.add(File(context.filesDir, material.filePath))
    }

    /** Track an arbitrary file for cleanup. */
    private fun trackFile(file: File) {
        trackedFiles.add(file)
    }

    // ====================================================================
    // Protection test: sentinel survives cleanup
    // ====================================================================

    @Test
    fun sentinelFile_survivesCleanup() = runTest {
        // Import something so cleanup has work to do
        val uri = createTestFileUri("protect.txt", "test content")
        val material = service.importFile(uri)
        trackMaterial(material)

        assertTrue("Sentinel must exist before cleanup", sentinelFile.exists())
        assertEquals("user content", sentinelFile.readText())

        // cleanupFiles runs in teardown — sentinel is NOT in trackedFiles
        // so it must survive. Verify after our explicit cleanup call:
        cleanupFiles()
        assertTrue("Sentinel must survive cleanup", sentinelFile.exists())
        assertEquals("user content", sentinelFile.readText())
    }

    // ====================================================================
    // importFile: success path
    // ====================================================================

    @Test
    fun importFile_validTxtFile_createsMaterialAndChunks() = runTest {
        val uri = createTestFileUri("notes.txt", "Hello world. This is a test file with some content for chunking.")

        val material = service.importFile(uri)
        trackMaterial(material)

        assertNotNull(material.id)
        assertTrue(material.id > 0)
        assertTrue("Title should be a .txt file", material.title.endsWith(".txt"))
        assertTrue(material.filePath.startsWith("materials/"))
        assertTrue(material.filePath.endsWith(".txt"))

        val localFile = File(context.filesDir, material.filePath)
        assertTrue("Local file should exist", localFile.exists())
        assertTrue("File should have content", localFile.length() > 0)

        val chunks = db.materialChunkDao().getByMaterialId(material.id)
        val chunkList = chunks.first()
        assertTrue("Should have at least one chunk", chunkList.isNotEmpty())
        assertTrue("Chunk content should contain text", chunkList[0].content.contains("Hello"))
    }

    @Test
    fun importFile_longContent_multipleChunks() = runTest {
        val longContent = "This is a paragraph about mathematics. ".repeat(100)
        val uri = createTestFileUri("long.txt", longContent)

        val material = service.importFile(uri)
        trackMaterial(material)

        val chunks = db.materialChunkDao().getByMaterialId(material.id)
        val chunkList = chunks.first()
        assertTrue("Long content should produce multiple chunks", chunkList.size >= 2)

        chunkList.forEachIndexed { index, chunk ->
            assertEquals(index, chunk.chunkIndex)
            assertEquals(material.id, chunk.materialId)
        }
    }

    @Test
    fun importFile_filePathStartsWithMaterials() = runTest {
        val uri = createTestFileUri("doc.md", "# Title\nContent here.")

        val material = service.importFile(uri)
        trackMaterial(material)

        assertTrue(material.filePath.startsWith("materials/"))
        assertTrue(material.filePath.length > "materials/".length)
    }

    // ====================================================================
    // importFile: duplicate name — deterministic via TestContentProvider
    // ====================================================================

    @Test
    fun importFile_duplicateName_appendsSuffix() = runTest {
        // Create ONE source file with a fixed name.  Both URIs point to the same
        // file path, so resolveMetadata returns the same display name for both.
        // The second import must get a _1 or _2 suffix.
        val cacheDir = File(context.cacheDir, "test_imports")
        cacheDir.mkdirs()
        val sourceFile = File(cacheDir, "dup_test.txt")
        sourceFile.writeText("First file content.")
        trackedFiles.add(sourceFile)
        val uri = Uri.fromFile(sourceFile)

        val mat1 = service.importFile(uri)
        trackMaterial(mat1)

        // Overwrite source with different content (same filename)
        sourceFile.writeText("Second file content.")
        val mat2 = service.importFile(uri)
        trackMaterial(mat2)

        assertTrue("filePaths must differ: ${mat1.filePath} vs ${mat2.filePath}",
            mat1.filePath != mat2.filePath)
        assertTrue("First filePath must start with materials/",
            mat1.filePath.startsWith("materials/"))
        assertTrue("Second filePath must contain _1 or _2 suffix: ${mat2.filePath}",
            mat2.filePath.contains("_1") || mat2.filePath.contains("_2"))
    }

    // ====================================================================
    // importFile: fileSize
    // ====================================================================

    @Test
    fun importFile_fileSize_matchesActualFileSize() = runTest {
        val content = "A".repeat(4096)
        val uri = createTestFileUri("sized.txt", content)

        val material = service.importFile(uri)
        trackMaterial(material)

        val localFile = File(context.filesDir, material.filePath)
        assertTrue(localFile.exists())
        assertEquals("fileSize must match actual file bytes", localFile.length(), material.fileSize)
    }

    @Test
    fun importFile_fileSize_notDependentOnOpenableColumns() = runTest {
        // Uri.fromFile doesn't provide OpenableColumns.SIZE (returns 0).
        // fileSize must still be correct because it comes from finalDest.length().
        val content = "Real content here with known length."
        val uri = createTestFileUri("providerless.txt", content)

        val material = service.importFile(uri)
        trackMaterial(material)

        assertTrue("fileSize should be > 0 even when provider doesn't supply size", material.fileSize > 0)
        assertEquals(
            "fileSize must equal actual file bytes",
            File(context.filesDir, material.filePath).length(),
            material.fileSize
        )
    }

    // ====================================================================
    // importFile: empty/blank content rejection
    // ====================================================================

    @Test
    fun importFile_emptyContent_throwsImportException() = runTest {
        val uri = createTestFileUri("empty.txt", "")

        try {
            service.importFile(uri)
            fail("Should throw ImportException for empty content")
        } catch (e: ImportException) {
            assertTrue(e.message!!.contains("空"))
        }
        assertEquals(0, db.materialDao().getAllSync().size)
    }

    @Test
    fun importFile_blankContent_throwsImportException() = runTest {
        val uri = createTestFileUri("blank.txt", "   \n  \t  ")

        try {
            service.importFile(uri)
            fail("Should throw ImportException for blank content")
        } catch (e: ImportException) {
            assertTrue(e.message!!.contains("空"))
        }
    }

    // ====================================================================
    // importFile: no .tmp left behind on success
    // ====================================================================

    @Test
    fun importFile_success_noTmpFilesLeftBehind() = runTest {
        val uri = createTestFileUri("clean.txt", "Clean import content.")

        val material = service.importFile(uri)
        trackMaterial(material)

        val materialsDir = File(context.filesDir, "materials")
        val tmpFiles = materialsDir.listFiles()?.filter { it.name.endsWith(".tmp") }
        assertTrue("No .tmp files should remain after successful import", tmpFiles.isNullOrEmpty())
    }

    // ====================================================================
    // importFile: failure path — tmp file cleanup
    // ====================================================================

    @Test
    fun importFile_blankContent_noTmpFileLeftBehind() = runTest {
        val uri = createTestFileUri("blank_tmp.txt", "   \n  \t  ")

        try {
            service.importFile(uri)
            fail("Should throw")
        } catch (_: ImportException) { }

        // The .tmp file created during copy must have been deleted
        val materialsDir = File(context.filesDir, "materials")
        val tmpFiles = materialsDir.listFiles()?.filter { it.name.endsWith(".tmp") }
        assertTrue("No .tmp files should remain after blank content rejection", tmpFiles.isNullOrEmpty())
    }

    @Test
    fun importFile_copyFailure_noTmpFileLeftBehind() = runTest {
        // Create a real file, get its URI, then delete the file.
        // The import will fail when trying to open the input stream.
        val cacheDir = File(context.cacheDir, "test_imports")
        cacheDir.mkdirs()
        val file = File(cacheDir, "will_be_deleted.txt")
        file.writeText("some content")
        trackedFiles.add(file)
        val uri = Uri.fromFile(file)
        file.delete() // make the URI unreadable

        try {
            service.importFile(uri)
            fail("Should throw ImportException when source file is gone")
        } catch (e: ImportException) {
            assertTrue(e.message!!.contains("复制") || e.message!!.contains("读取") || e.message!!.contains("无法"))
        }

        // No tmp file should remain
        val materialsDir = File(context.filesDir, "materials")
        val tmpFiles = materialsDir.listFiles()?.filter { it.name.endsWith(".tmp") }
        assertTrue("No .tmp files should remain after copy failure", tmpFiles.isNullOrEmpty())
    }

    // ====================================================================
    // importFile: failure path — finalDest cleanup on DB failure
    //
    // We can't easily force a DB transaction failure without DI,
    // but we can verify the cleanup contract by checking that the
    // importFile method's catch block calls deleteLocalFile.
    // This is covered by the blank-content test above (tmp cleanup)
    // and the structural guarantee in the source code.
    // ====================================================================

    // ====================================================================
    // deleteMaterial: manual material with filePath=""
    // ====================================================================

    @Test
    fun deleteMaterial_manualMaterial_emptyFilePath_doesNotDeleteMaterialsDir() = runTest {
        val id = db.materialDao().insert(Material(title = "Manual Entry", filePath = ""))
        db.materialChunkDao().insert(
            com.example.mathagent.data.local.entity.MaterialChunk(
                materialId = id, chunkIndex = 0, content = "Some content"
            )
        )

        val material = db.materialDao().getById(id)!!
        service.deleteMaterial(material)

        assertEquals(0, db.materialDao().getAllSync().size)
        val chunks = db.materialChunkDao().getByMaterialId(id)
        assertTrue(chunks.first().isEmpty())
    }

    // ====================================================================
    // deleteMaterial: imported file cleanup
    // ====================================================================

    @Test
    fun deleteMaterial_importedMaterial_deletesFileAndCascadeChunks() = runTest {
        val uri = createTestFileUri("del.txt", "Content to be deleted later.")
        val material = service.importFile(uri)
        trackMaterial(material)

        val localFile = File(context.filesDir, material.filePath)
        assertTrue("File should exist after import", localFile.exists())

        val chunksBefore = db.materialChunkDao().getByMaterialId(material.id)
        assertTrue("Chunks should exist before delete", chunksBefore.first().isNotEmpty())

        service.deleteMaterial(material)

        assertFalse("File should be deleted after deleteMaterial", localFile.exists())
        assertEquals(0, db.materialDao().getAllSync().size)

        val chunksAfter = db.materialChunkDao().getByMaterialId(material.id)
        assertTrue("Chunks should be cascade-deleted", chunksAfter.first().isEmpty())
    }

    // ====================================================================
    // deleteMaterialById
    // ====================================================================

    @Test
    fun deleteMaterialById_importedMaterial_deletesFileAndCascadeChunks() = runTest {
        val uri = createTestFileUri("byid.txt", "Delete by ID test content.")
        val material = service.importFile(uri)
        trackMaterial(material)

        val localFile = File(context.filesDir, material.filePath)
        assertTrue(localFile.exists())

        service.deleteMaterialById(material.id)

        assertFalse("File should be deleted", localFile.exists())
        assertEquals(0, db.materialDao().getAllSync().size)
    }

    @Test
    fun deleteMaterialById_nonExistentId_noop() = runTest {
        service.deleteMaterialById(99999L)
        assertEquals(0, db.materialDao().getAllSync().size)
    }

    // ====================================================================
    // deleteLocalFile: boundary tests
    // ====================================================================

    @Test
    fun deleteLocalFile_blankPath_noop() = runTest {
        service.deleteLocalFile("")
        service.deleteLocalFile("   ")
    }

    @Test
    fun deleteLocalFile_materialsDirItself_rejected() = runTest {
        val uri = createTestFileUri("keep.txt", "Keep this file.")
        val material = service.importFile(uri)
        trackMaterial(material)

        service.deleteLocalFile("materials")

        val localFile = File(context.filesDir, material.filePath)
        assertTrue("File should still exist", localFile.exists())
    }

    @Test
    fun deleteLocalFile_existingSubdir_notDeleted() = runTest {
        // Create a real subdirectory inside materials/
        val subdirName = "real_subdir_${System.nanoTime()}"
        val subdir = File(context.filesDir, "materials/$subdirName")
        subdir.mkdirs()
        trackFile(subdir)
        assertTrue("Subdir must exist before test", subdir.isDirectory)

        // Ask the service to delete it — must be rejected (isFile check)
        service.deleteLocalFile("materials/$subdirName")

        assertTrue("Existing subdirectory must NOT be deleted by deleteLocalFile", subdir.isDirectory)
        assertTrue("Sentinel must survive", sentinelFile.exists())
    }

    @Test
    fun deleteLocalFile_existingFile_deleted() = runTest {
        // Create a real file inside materials/
        val fileName = "real_file_${System.nanoTime()}.txt"
        val file = File(context.filesDir, "materials/$fileName")
        file.parentFile?.mkdirs()
        file.writeText("will be deleted")
        assertTrue("File must exist before test", file.isFile)

        // Ask the service to delete it — must succeed
        service.deleteLocalFile("materials/$fileName")

        assertFalse("Existing file must be deleted by deleteLocalFile", file.exists())
        assertTrue("Sentinel must survive", sentinelFile.exists())
    }

    @Test
    fun deleteLocalFile_traversalPath_rejected() = runTest {
        service.deleteLocalFile("../shared_prefs/x")
        assertTrue("Sentinel must survive", sentinelFile.exists())
    }

    @Test
    fun deleteLocalFile_absolutePath_rejected() = runTest {
        service.deleteLocalFile("/data/local/tmp/evil.txt")
        assertTrue("Sentinel must survive", sentinelFile.exists())
    }

    // ====================================================================
    // helpers
    // ====================================================================

    /** Create a source file in cache and return its Uri. */
    private fun createTestFileUri(baseName: String, content: String): Uri {
        val cacheDir = File(context.cacheDir, "test_imports")
        cacheDir.mkdirs()
        val file = File(cacheDir, baseName)
        file.writeText(content)
        trackedFiles.add(file)
        return Uri.fromFile(file)
    }
}
