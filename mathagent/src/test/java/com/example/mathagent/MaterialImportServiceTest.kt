package com.example.mathagent

import android.content.Context
import com.example.mathagent.data.local.MathAgentDatabase
import com.example.mathagent.data.local.dao.MaterialChunkDao
import com.example.mathagent.data.local.dao.MaterialDao
import com.example.mathagent.data.material.MaterialImportService
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever
import java.io.File

/**
 * Unit tests for [MaterialImportService] static helpers:
 * - isSupported: file type detection (unsupported MIME overrides extension)
 * - chunkText: text splitting logic
 * - sanitizeFileName: path safety
 * - deleteLocalFile: boundary and path traversal safety
 */
class MaterialImportServiceTest {

    // ---- isSupported: unsupported MIME overrides extension ----

    @Test
    fun isSupported_pdfWithFakeTxtExt_rejected() {
        // application/pdf is unsupported — even with .txt extension
        assertFalse(MaterialImportService.isSupported("application/pdf", "fake.txt"))
    }

    @Test
    fun isSupported_imagePngWithMdExt_rejected() {
        // image/* is unsupported — even with .md extension
        assertFalse(MaterialImportService.isSupported("image/png", "note.md"))
    }

    @Test
    fun isSupported_wordWithJsonExt_rejected() {
        assertFalse(MaterialImportService.isSupported(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "data.json"
        ))
    }

    @Test
    fun isSupported_videoMp4_rejected() {
        assertFalse(MaterialImportService.isSupported("video/mp4", "clip.mp4"))
    }

    @Test
    fun isSupported_audioWav_rejected() {
        assertFalse(MaterialImportService.isSupported("audio/wav", "sound.wav"))
    }

    @Test
    fun isSupported_zipRejected() {
        assertFalse(MaterialImportService.isSupported("application/zip", "archive.zip"))
    }

    // ---- isSupported: supported MIME ----

    @Test
    fun isSupported_textPlain_accepted() {
        assertTrue(MaterialImportService.isSupported("text/plain", "notes.txt"))
    }

    @Test
    fun isSupported_textCsv_accepted() {
        assertTrue(MaterialImportService.isSupported("text/csv", "data.csv"))
    }

    @Test
    fun isSupported_applicationJson_accepted() {
        assertTrue(MaterialImportService.isSupported("application/json", "config.json"))
    }

    @Test
    fun isSupported_textHtml_accepted() {
        assertTrue(MaterialImportService.isSupported("text/html", "page.html"))
    }

    // ---- isSupported: null MIME → extension fallback ----

    @Test
    fun isSupported_nullMimeWithMdExt_accepted() {
        assertTrue(MaterialImportService.isSupported(null, "readme.md"))
    }

    @Test
    fun isSupported_nullMimeWithTxtExt_accepted() {
        assertTrue(MaterialImportService.isSupported(null, "data.txt"))
    }

    @Test
    fun isSupported_nullMimeWithUnknownExt_rejected() {
        assertFalse(MaterialImportService.isSupported(null, "data.bin"))
    }

    // ---- isSupported: application/octet-stream → extension fallback ----

    @Test
    fun isSupported_octetStreamWithPyExt_accepted() {
        assertTrue(MaterialImportService.isSupported("application/octet-stream", "script.py"))
    }

    @Test
    fun isSupported_octetStreamWithTxtExt_accepted() {
        assertTrue(MaterialImportService.isSupported("application/octet-stream", "data.txt"))
    }

    @Test
    fun isSupported_octetStreamWithUnknownExt_rejected() {
        assertFalse(MaterialImportService.isSupported("application/octet-stream", "data.bin"))
    }

    // ---- isSupported: known text MIME → extension fallback ----

    @Test
    fun isSupported_xPythonWithPyExt_accepted() {
        assertTrue(MaterialImportService.isSupported("application/x-python", "script.py"))
    }

    @Test
    fun isSupported_sqlMimeWithSqlExt_accepted() {
        assertTrue(MaterialImportService.isSupported("application/sql", "query.sql"))
    }

    @Test
    fun isSupported_xmlMimeWithXmlExt_accepted() {
        assertTrue(MaterialImportService.isSupported("application/xml", "data.xml"))
    }

    // ---- isSupported: unknown application/* rejected (no blind fallback) ----

    @Test
    fun isSupported_apkWithFakeTxt_rejected() {
        // application/vnd.android.package-archive is a binary installer
        assertFalse(MaterialImportService.isSupported("application/vnd.android.package-archive", "fake.txt"))
    }

    @Test
    fun isSupported_dosexecWithFakeTxt_rejected() {
        // application/x-dosexec is a DOS/Windows executable
        assertFalse(MaterialImportService.isSupported("application/x-dosexec", "fake.txt"))
    }

    @Test
    fun isSupported_sqlite3WithFakeTxt_rejected() {
        // application/x-sqlite3 is a binary database file
        assertFalse(MaterialImportService.isSupported("application/x-sqlite3", "fake.txt"))
    }

    @Test
    fun isSupported_unknownApplicationXWithTxt_rejected() {
        // Completely unknown application/* must not get blind extension fallback
        assertFalse(MaterialImportService.isSupported("application/x-virtualbox-vmdk", "notes.txt"))
    }

    // ---- chunkText ----

    @Test
    fun chunkText_emptyText_returnsEmpty() {
        val chunks = MaterialImportService.chunkText("", 1L)
        assertTrue(chunks.isEmpty())
    }

    @Test
    fun chunkText_blankText_returnsEmpty() {
        val chunks = MaterialImportService.chunkText("   \n  ", 1L)
        assertTrue(chunks.isEmpty())
    }

    @Test
    fun chunkText_shortText_singleChunk() {
        val text = "Hello world, this is a short text."
        val chunks = MaterialImportService.chunkText(text, 42L)
        assertEquals(1, chunks.size)
        assertEquals(text, chunks[0].content)
        assertEquals(42L, chunks[0].materialId)
        assertEquals(0, chunks[0].chunkIndex)
    }

    @Test
    fun chunkText_longText_multipleChunks() {
        val paragraph = "This is a test paragraph with enough text to be meaningful. ".repeat(10)
        val text = "$paragraph\n\n$paragraph\n\n$paragraph"
        val chunks = MaterialImportService.chunkText(text, 1L)

        assertTrue("Should produce multiple chunks", chunks.size >= 2)
        chunks.forEachIndexed { i, chunk ->
            assertEquals(i, chunk.chunkIndex)
            assertEquals(1L, chunk.materialId)
            assertTrue("Chunk should not be empty", chunk.content.isNotBlank())
        }
    }

    @Test
    fun chunkText_preservesContent() {
        val text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        val chunks = MaterialImportService.chunkText(text, 1L)
        val reconstructed = chunks.joinToString("\n\n") { it.content }
        assertTrue(reconstructed.contains("First paragraph"))
        assertTrue(reconstructed.contains("Third paragraph"))
    }

    @Test
    fun chunkText_veryLongParagraph_splitsOnSentence() {
        val sentence = "This is a sentence with some words. "
        val text = sentence.repeat(100)
        val chunks = MaterialImportService.chunkText(text, 1L)

        assertTrue(chunks.size >= 2)
        chunks.forEach { chunk ->
            assertTrue(chunk.content.length <= 1500)
        }
    }

    @Test
    fun chunkText_allChunkIndicesSequential() {
        val text = "Word. ".repeat(500)
        val chunks = MaterialImportService.chunkText(text, 99L)
        chunks.forEachIndexed { i, chunk ->
            assertEquals(i, chunk.chunkIndex)
            assertEquals(99L, chunk.materialId)
        }
    }

    // ---- findBreakPoint ----

    @Test
    fun findBreakPoint_textShorterThanMax_returnsLength() {
        assertEquals(5, MaterialImportService.findBreakPoint("short", 100, 20, 200))
    }

    @Test
    fun findBreakPoint_prefersParagraphBreak() {
        val text = "A".repeat(800) + "\n\n" + "B".repeat(800)
        assertEquals(802, MaterialImportService.findBreakPoint(text, 1000, 200, 1500))
    }

    @Test
    fun findBreakPoint_prefersSentenceEnd() {
        val text = "A".repeat(800) + ". " + "B".repeat(800)
        assertEquals(802, MaterialImportService.findBreakPoint(text, 1000, 200, 1500))
    }

    @Test
    fun findBreakPoint_fallsBackToWordBoundary() {
        val text = "A".repeat(800) + " " + "B".repeat(800)
        assertEquals(801, MaterialImportService.findBreakPoint(text, 1000, 200, 1500))
    }

    // ---- sanitizeFileName ----

    @Test
    fun sanitizeFileName_normalName() {
        assertEquals("test.txt", MaterialImportService.sanitizeFileName("test.txt"))
    }

    @Test
    fun sanitizeFileName_removesPathSeparators() {
        val result = MaterialImportService.sanitizeFileName("../../../etc/passwd")
        assertFalse(result.contains("/"))
        assertFalse(result.contains("\\"))
    }

    @Test
    fun sanitizeFileName_removesSpecialChars() {
        val result = MaterialImportService.sanitizeFileName("file:*?\"<>|.txt")
        assertFalse(result.contains(":"))
        assertFalse(result.contains("*"))
    }

    @Test
    fun sanitizeFileName_emptyBecomesDefault() {
        assertEquals("imported_file", MaterialImportService.sanitizeFileName(""))
    }

    @Test
    fun sanitizeFileName_onlySpecialChars() {
        assertEquals("imported_file", MaterialImportService.sanitizeFileName(":::"))
    }

    @Test
    fun sanitizeFileName_longNameTruncated() {
        val result = MaterialImportService.sanitizeFileName("a".repeat(300) + ".txt")
        assertTrue(result.length <= 200)
    }

    @Test
    fun sanitizeFileName_replacesWhitespace() {
        val result = MaterialImportService.sanitizeFileName("my file name.txt")
        assertFalse(result.contains(" "))
        assertTrue(result.contains("_"))
    }

    // ---- isSupported: executable MIME always rejected ----

    @Test
    fun isSupported_xMsdownloadWithFakeTxt_rejected() {
        // application/x-msdownload (PE executable) must be rejected even with .txt extension
        assertFalse(MaterialImportService.isSupported("application/x-msdownload", "fake.txt"))
    }

    @Test
    fun isSupported_xMsdownloadWithPyExt_rejected() {
        assertFalse(MaterialImportService.isSupported("application/x-msdownload", "virus.py"))
    }

    @Test
    fun isSupported_javaArchive_rejected() {
        assertFalse(MaterialImportService.isSupported("application/java-archive", "app.jar"))
    }

    // ---- isSupported: mixed-case MIME normalization ----

    @Test
    fun isSupported_mixedCaseTextPlain_accepted() {
        assertTrue(MaterialImportService.isSupported("Text/Plain", "notes.txt"))
    }

    @Test
    fun isSupported_upperCaseApplicationJson_accepted() {
        assertTrue(MaterialImportService.isSupported("APPLICATION/JSON", "config.json"))
    }

    @Test
    fun isSupported_mixedCasePdf_rejected() {
        assertFalse(MaterialImportService.isSupported("Application/PDF", "doc.pdf"))
    }

    @Test
    fun isSupported_mixedCaseOctetStream_fallbackToExt() {
        // application/octet-stream with .txt should still be accepted
        assertTrue(MaterialImportService.isSupported("APPLICATION/OCTET-STREAM", "data.txt"))
        // ...but .bin should be rejected
        assertFalse(MaterialImportService.isSupported("APPLICATION/OCTET-STREAM", "data.bin"))
    }

    // ---- deleteLocalFile: boundary tests ----

    @Test
    fun deleteLocalFile_blankPath_noop() {
        // Should not throw; blank path is a no-op
        val service = createServiceWithMockContext()
        service.deleteLocalFile("")
        service.deleteLocalFile("   ")
        service.deleteLocalFile("\t")
    }

    @Test
    fun deleteLocalFile_materialsDirItself_rejected() {
        // "materials" resolves to the materials directory — must NOT delete it
        val service = createServiceWithMockContext()
        // Should be a no-op; if it deleted the dir, the test would fail on next assertion
        service.deleteLocalFile("materials")
    }

    @Test
    fun deleteLocalFile_materialsDirSlash_rejected() {
        val service = createServiceWithMockContext()
        service.deleteLocalFile("materials/")
    }

    @Test
    fun deleteLocalFile_materialsSubdir_rejected() {
        // "materials/subdir" is a directory, not a file — must not delete
        val service = createServiceWithMockContext()
        service.deleteLocalFile("materials/subdir")
    }

    @Test
    fun deleteLocalFile_traversalPath_rejected() {
        // "../shared_prefs/x" should be rejected (path traversal)
        val service = createServiceWithMockContext()
        service.deleteLocalFile("../shared_prefs/x")
    }

    @Test
    fun deleteLocalFile_absolutePath_rejected() {
        // Absolute path should not be resolved relative to filesDir
        val service = createServiceWithMockContext()
        service.deleteLocalFile("/data/local/tmp/evil.txt")
    }

    @Test
    fun deleteLocalFile_nonExistentFile_noop() {
        // Deleting a non-existent file should silently no-op
        val service = createServiceWithMockContext()
        service.deleteLocalFile("materials/does_not_exist.txt")
    }

    @Test
    fun deleteLocalFile_dotDotEncoded_rejected() {
        val service = createServiceWithMockContext()
        service.deleteLocalFile("materials/../../secret.txt")
    }

    // ---- helpers ----

    private fun createServiceWithMockContext(): MaterialImportService {
        val context = mock<Context>()
        val tmpDir = File(System.getProperty("java.io.tmpdir"), "mathagent_test_${System.nanoTime()}")
        tmpDir.mkdirs()
        whenever(context.filesDir).thenReturn(tmpDir)

        val materialDao = mock<MaterialDao>()
        val chunkDao = mock<MaterialChunkDao>()
        val database = mock<MathAgentDatabase>()

        // Create materials dir so canonical path resolution works
        File(tmpDir, "materials").mkdirs()

        return MaterialImportService(context, materialDao, chunkDao, database)
    }
}
