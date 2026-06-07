package com.example.mathagent.data.repository

import com.example.mathagent.data.local.dao.MaterialChunkDao
import com.example.mathagent.data.local.dao.MaterialDao
import com.example.mathagent.data.local.entity.Material
import com.example.mathagent.data.local.entity.MaterialChunk
import kotlinx.coroutines.flow.Flow

class MaterialRepository(
    private val materialDao: MaterialDao,
    private val chunkDao: MaterialChunkDao
) {
    fun getAllMaterials(): Flow<List<Material>> = materialDao.getAll()

    suspend fun getMaterial(id: Long): Material? = materialDao.getById(id)

    suspend fun insertMaterial(material: Material): Long = materialDao.insert(material)

    suspend fun updateMaterial(material: Material) = materialDao.update(material)

    /**
     * Delete material. Chunks are cascade-deleted by Room FK constraint.
     */
    suspend fun deleteMaterial(material: Material) {
        materialDao.delete(material)
    }

    /**
     * Delete material by id. Chunks are cascade-deleted by Room FK constraint.
     */
    suspend fun deleteMaterialById(id: Long) {
        materialDao.deleteById(id)
    }

    fun materialCount(): Flow<Int> = materialDao.count()

    fun getChunks(materialId: Long): Flow<List<MaterialChunk>> =
        chunkDao.getByMaterialId(materialId)

    suspend fun getChunksSync(materialId: Long): List<MaterialChunk> =
        chunkDao.getChunksByMaterialId(materialId)

    suspend fun insertChunks(chunks: List<MaterialChunk>) = chunkDao.insertAll(chunks)

    suspend fun insertChunk(chunk: MaterialChunk): Long = chunkDao.insert(chunk)

    suspend fun getChunkById(id: Long): MaterialChunk? = chunkDao.getById(id)

    suspend fun searchChunks(query: String, limit: Int = 20): List<MaterialChunk> =
        chunkDao.search(query, limit)
}
