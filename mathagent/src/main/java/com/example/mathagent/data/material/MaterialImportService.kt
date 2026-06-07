package com.example.mathagent.data.material

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.room.withTransaction
import com.example.mathagent.data.local.MathAgentDatabase
import com.example.mathagent.data.local.dao.MaterialChunkDao
import com.example.mathagent.data.local.dao.MaterialDao
import com.example.mathagent.data.local.entity.Material
import com.example.mathagent.data.local.entity.MaterialChunk
import java.io.File

/**
 * Handles file import for learning materials:
 * - Reads file content from a content URI
 * - Copies the file to app-private storage
 * - Splits text content into chunks for search/AI retrieval
 * - Records metadata in Room (atomically with chunks)
 *
 * Supported: text/plain, text (any subtype), application/json, and common text extensions.
 * PDF/Word/images/audio/video are rejected with a readable error.
 */
class MaterialImportService(
    private val context: Context,
    private val materialDao: MaterialDao,
    private val chunkDao: MaterialChunkDao,
    private val database: MathAgentDatabase
) {
    /**
     * Import a file from a content URI.
     *
     * I/O flow (single-pass — the URI is read exactly once):
     * 1. Resolve metadata (fileName, mimeType) from the content URI.
     * 2. Check supported type.
     * 3. Copy URI content to a unique .tmp file in the materials directory.
     * 4. Read text from the .tmp file and validate non-blank.
     * 5. Generate chunks from the .tmp file content.
     * 6. Rename .tmp to final destination.
     * 7. Insert Material + Chunks atomically in a Room transaction.
     *
     * Cleanup guarantees:
     * - Steps 3–5 failure → delete the .tmp file.
     * - Step 7 failure → delete the final destination file.
     *
     * @return the imported [Material] entity with real fileSize from the copied file.
     * @throws ImportException on unsupported type, read failure, or empty content
     */
    suspend fun importFile(uri: Uri): Material {
        // 1. Resolve metadata
        val meta = resolveMetadata(uri)

        // 2. Check supported type
        if (!isSupported(meta.mimeType, meta.fileName)) {
            throw ImportException("不支持的文件类型: ${meta.mimeType ?: "未知"}。目前支持纯文本、JSON、CSV、Markdown 等文本文件。")
        }

        val dir = File(context.filesDir, "materials")
        if (!dir.exists()) dir.mkdirs()

        val safeName = sanitizeFileName(meta.fileName)
        val finalDest = resolveUniqueDest(dir, safeName)
        val tmpFile = File(dir, "${finalDest.name}.tmp")

        // 3. Copy URI → .tmp (single read of the URI)
        try {
            context.contentResolver.openInputStream(uri)?.use { input ->
                tmpFile.outputStream().use { output ->
                    input.copyTo(output)
                }
            } ?: throw ImportException("无法读取源文件")
        } catch (e: ImportException) {
            tmpFile.delete()
            throw e
        } catch (e: Exception) {
            tmpFile.delete()
            throw ImportException("复制文件失败: ${e.message}")
        }

        // 4. Read text from .tmp and validate
        val content = try {
            tmpFile.bufferedReader().readText()
        } catch (e: Exception) {
            tmpFile.delete()
            throw ImportException("读取临时文件失败: ${e.message}")
        }
        if (content.isBlank()) {
            tmpFile.delete()
            throw ImportException("文件内容为空")
        }

        // 5. Generate chunks (from .tmp content — no second URI read)
        val chunks = chunkText(content, 0L) // materialId placeholder, updated in transaction

        // 6. Rename .tmp → finalDest
        if (!tmpFile.renameTo(finalDest)) {
            tmpFile.delete()
            throw ImportException("重命名临时文件失败")
        }

        val relativePath = "materials/${finalDest.name}"
        val realFileSize = finalDest.length() // actual copied file size

        // 7. Insert Material + Chunks atomically
        try {
            val material = Material(
                title = meta.fileName,
                subject = "",
                filePath = relativePath,
                fileType = meta.mimeType ?: "text/plain",
                fileSize = realFileSize,
                description = ""
            )

            val materialId = database.withTransaction {
                val id = materialDao.insert(material)
                val realChunks = chunks.map { it.copy(materialId = id) }
                if (realChunks.isNotEmpty()) {
                    chunkDao.insertAll(realChunks)
                }
                id
            }

            return material.copy(id = materialId)
        } catch (e: Exception) {
            // DB write failed — clean up the final file
            deleteLocalFile(relativePath)
            throw ImportException("保存到数据库失败: ${e.message}", e)
        }
    }

    /**
     * Delete a material: remove local file copy, then DB record (chunks cascade via FK).
     */
    suspend fun deleteMaterial(material: Material) {
        deleteLocalFile(material.filePath)
        materialDao.delete(material)
    }

    /**
     * Delete a material by id: remove local file copy, then DB record.
     */
    suspend fun deleteMaterialById(id: Long) {
        val material = materialDao.getById(id)
        if (material != null) {
            deleteLocalFile(material.filePath)
            materialDao.deleteById(id)
        }
    }

    /**
     * Delete a local file safely.
     *
     * - Blank/no-op if [relativePath] is empty or blank.
     * - Only deletes **regular files** under `context.filesDir/materials/`.
     * - Rejects the materials directory itself and any subdirectories.
     * - Uses canonical path to reject `../` traversal and absolute paths.
     */
    internal fun deleteLocalFile(relativePath: String) {
        if (relativePath.isBlank()) return

        val materialsDir = File(context.filesDir, "materials")
        val file = File(context.filesDir, relativePath)

        try {
            val canonicalMaterials = materialsDir.canonicalFile
            val canonicalTarget = file.canonicalFile

            // Must be strictly inside materialsDir (not the dir itself)
            if (!canonicalTarget.path.startsWith(canonicalMaterials.path + File.separator)) return

            // Only delete regular files — never directories
            if (!canonicalTarget.isFile) return

            canonicalTarget.delete()
        } catch (_: Exception) {
            // Best-effort; path may be invalid or file already gone
        }
    }

    /**
     * Resolve a unique destination file in [dir] for [safeName].
     * If the file already exists, appends `_1`, `_2`, etc.
     */
    private fun resolveUniqueDest(dir: File, safeName: String): File {
        val dest = File(dir, safeName)
        if (!dest.exists()) return dest

        val base = dest.nameWithoutExtension
        val ext = dest.extension.let { if (it.isNotEmpty()) ".$it" else "" }
        var counter = 1
        var candidate = File(dir, "${base}_$counter$ext")
        while (candidate.exists()) {
            counter++
            candidate = File(dir, "${base}_$counter$ext")
        }
        return candidate
    }

    /**
     * Resolve file metadata from the content URI.
     *
     * NOTE: [OpenableColumns.SIZE] is unreliable — many providers (including file:// URIs)
     * return 0 or omit it entirely.  The caller MUST use `finalDest.length()` for the real
     * file size after copying, not the value from [FileMeta.size].
     */
    private fun resolveMetadata(uri: Uri): FileMeta {
        var fileName = "unknown.txt"
        var mimeType: String? = null
        var size = 0L

        context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) {
                val nameIdx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                val sizeIdx = cursor.getColumnIndex(OpenableColumns.SIZE)
                if (nameIdx >= 0) fileName = cursor.getString(nameIdx) ?: fileName
                if (sizeIdx >= 0) size = cursor.getLong(sizeIdx)
            }
        }

        mimeType = context.contentResolver.getType(uri)

        return FileMeta(fileName = fileName, mimeType = mimeType, size = size)
    }

    companion object {
        /** MIME types that are always accepted (direct match, no extension fallback needed). */
        private val SUPPORTED_MIME_PREFIXES = listOf("text/", "application/json")

        /** File extensions accepted during extension fallback. */
        private val SUPPORTED_EXTENSIONS = setOf(
            "txt", "json", "csv", "md", "markdown", "xml", "html", "htm",
            "log", "ini", "cfg", "conf", "yaml", "yml", "toml",
            "py", "kt", "java", "js", "ts", "c", "cpp", "h", "go", "rs", "rb",
            "sh", "bat", "ps1", "sql", "r", "tex", "bib"
        )

        /**
         * Known text-based MIME types allowed to fall through to extension check.
         * These are NOT caught by [SUPPORTED_MIME_PREFIXES] (which only covers text/any
         * and application/json) but are legitimate text formats.
         *
         * Only these specific MIME types + null + application/octet-stream get extension
         * fallback.  Any other unknown application/anything is rejected to avoid
         * accidentally accepting binary formats disguised with a .txt extension.
         *
         * All entries MUST be lowercase.
         */
        private val KNOWN_TEXT_MIME = setOf(
            "application/x-python",
            "application/sql",
            "application/xml",
            "application/javascript",
            "application/typescript",
            "application/x-sh",
            "application/x-yaml",
            "application/x-toml",
            "application/x-markdown",
            "application/x-latex",
            "application/x-bibtex",
            "application/x-subrip",             // .srt subtitles
            "application/x-httpd-php",
            "application/x-ns-proxy-autoconfig"  // .pac
        )

        /** MIME types that are explicitly unsupported (binary formats).
         *  Checked FIRST — overrides extension fallback.
         *  application/octet-stream is intentionally NOT here: it is the
         *  generic fallback for unknown types and must be handled by extension check.
         *  All entries MUST be lowercase (comparison is case-insensitive). */
        private val UNSUPPORTED_MIME_PREFIXES = listOf(
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats",
            "application/vnd.ms-",
            "image/", "audio/", "video/",
            "application/zip", "application/x-rar", "application/gzip",
            "application/x-msdownload", "application/x-executable",
            "application/x-elf", "application/x-mach-binary",
            "application/java-archive", "application/x-shockwave-flash",
            "application/vnd.android.package-archive",
            "application/x-dosexec",
            "application/x-sqlite3"
        )

        private const val CHUNK_TARGET_SIZE = 1000
        private const val CHUNK_MIN_SIZE = 200
        private const val CHUNK_MAX_SIZE = 1500

        /**
         * Check if a file is supported for import.
         *
         * Priority:
         * 1. Explicit unsupported MIME -> reject (even if extension looks safe)
         * 2. Supported MIME prefix (text/any, application/json) -> accept
         * 3. Known text MIME (application/x-python, application/sql, etc.) -> extension fallback
         * 4. null or application/octet-stream -> extension fallback
         * 5. Any other MIME -> reject
         *
         * MIME comparison is case-insensitive.
         */
        fun isSupported(mimeType: String?, fileName: String): Boolean {
            val lowerMime = mimeType?.lowercase()

            // 1. Explicit unsupported MIME — reject first
            if (lowerMime != null && UNSUPPORTED_MIME_PREFIXES.any { lowerMime.startsWith(it) }) {
                return false
            }

            // 2. Supported MIME prefix (text/any, application/json)
            if (lowerMime != null && SUPPORTED_MIME_PREFIXES.any { lowerMime.startsWith(it) }) {
                return true
            }

            // 3–4. Extension fallback only for: null, application/octet-stream, known text MIME
            if (lowerMime != null &&
                lowerMime != "application/octet-stream" &&
                lowerMime !in KNOWN_TEXT_MIME
            ) {
                return false
            }

            val ext = fileName.substringAfterLast('.', "").lowercase()
            return ext in SUPPORTED_EXTENSIONS
        }

        /**
         * Split text into chunks of ~CHUNK_TARGET_SIZE characters,
         * breaking at paragraph or sentence boundaries.
         */
        fun chunkText(text: String, materialId: Long): List<MaterialChunk> {
            if (text.isBlank()) return emptyList()

            val chunks = mutableListOf<MaterialChunk>()
            var remaining = text.trim()
            var index = 0

            while (remaining.isNotEmpty()) {
                if (remaining.length <= CHUNK_MAX_SIZE) {
                    chunks.add(MaterialChunk(
                        materialId = materialId,
                        chunkIndex = index,
                        content = remaining.trim()
                    ))
                    break
                }

                val breakAt = findBreakPoint(remaining, CHUNK_TARGET_SIZE, CHUNK_MIN_SIZE, CHUNK_MAX_SIZE)
                val segment = remaining.substring(0, breakAt).trim()
                if (segment.isNotEmpty()) {
                    chunks.add(MaterialChunk(
                        materialId = materialId,
                        chunkIndex = index,
                        content = segment
                    ))
                    index++
                }
                remaining = remaining.substring(breakAt).trimStart()
            }

            return chunks
        }

        internal fun findBreakPoint(text: String, target: Int, min: Int, max: Int): Int {
            if (text.length <= max) return text.length

            val searchStart = min.coerceAtMost(text.length)
            val searchEnd = max.coerceAtMost(text.length)
            val searchRange = searchStart until searchEnd

            val paraIdx = text.lastIndexOf("\n\n", searchEnd)
            if (paraIdx in searchRange) return paraIdx + 2

            val nlIdx = text.lastIndexOf("\n", searchEnd)
            if (nlIdx in searchRange) return nlIdx + 1

            for (i in (searchEnd - 1).coerceAtLeast(searchStart) downTo searchStart) {
                if (text[i] in ".!?" && i + 1 < text.length && text[i + 1] == ' ') {
                    return i + 2
                }
            }

            val spaceIdx = text.lastIndexOf(' ', searchEnd)
            if (spaceIdx in searchRange) return spaceIdx + 1

            return max
        }

        internal fun sanitizeFileName(name: String): String {
            val sanitized = name
                .replace(Regex("[\\\\/:*?\"<>|]"), "_")
                .replace(Regex("\\s+"), "_")
                .trim('.', '_', ' ')
            return if (sanitized.isEmpty()) "imported_file" else sanitized.take(200)
        }
    }

    private data class FileMeta(
        val fileName: String,
        val mimeType: String?,
        val size: Long
    )
}

class ImportException(message: String, cause: Throwable? = null) : Exception(message, cause)
