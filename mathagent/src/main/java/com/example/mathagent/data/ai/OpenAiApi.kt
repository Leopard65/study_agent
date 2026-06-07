package com.example.mathagent.data.ai

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Interface for AI chat completion clients.
 * Enables testability: real implementation delegates to [OpenAiApi],
 * tests can substitute fakes or use MockWebServer.
 */
interface OpenAiClient {
    suspend fun chatCompletion(messages: List<ChatMessage>): String
}

/**
 * OpenAI-compatible API client for /chat/completions.
 * All errors are mapped to user-readable [AiException] without leaking API Key.
 */
class OpenAiApi(
    private val baseUrl: String = DEFAULT_BASE_URL,
    private val apiKey: String,
    private val model: String = DEFAULT_MODEL,
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()
) : OpenAiClient {
    /**
     * Send a chat completion request and return the assistant's reply text.
     * @throws AiException on any failure
     */
    override suspend fun chatCompletion(messages: List<ChatMessage>): String = withContext(Dispatchers.IO) {
        val url = buildUrl()

        val messagesArray = JSONArray()
        for (msg in messages) {
            messagesArray.put(JSONObject().apply {
                put("role", msg.role)
                put("content", msg.content)
            })
        }

        val body = JSONObject().apply {
            put("model", model)
            put("messages", messagesArray)
            put("temperature", 0.7)
            put("max_tokens", 2048)
        }.toString()

        val request = Request.Builder()
            .url(url)
            .addHeader("Authorization", "Bearer $apiKey")
            .addHeader("Content-Type", "application/json")
            .post(body.toRequestBody("application/json".toMediaType()))
            .build()

        try {
            val response = client.newCall(request).execute()
            val responseBody = response.body?.string() ?: ""

            if (!response.isSuccessful) {
                throw mapHttpError(response.code, responseBody, apiKey)
            }

            parseResponse(responseBody)
        } catch (e: AiException) {
            throw e
        } catch (e: IOException) {
            throw AiException("网络连接失败，请检查网络设置", AiErrorType.NETWORK_ERROR, e)
        } catch (e: Exception) {
            throw AiException("请求异常: ${scrubSecrets(e.message ?: "", apiKey)}", AiErrorType.UNKNOWN, e)
        }
    }

    private fun buildUrl(): String {
        val base = baseUrl.trimEnd('/')
        return if (base.endsWith("/chat/completions")) base else "$base/chat/completions"
    }

    companion object {
        const val DEFAULT_BASE_URL = "https://api.openai.com/v1"
        const val DEFAULT_MODEL = "gpt-4o-mini"

        /**
         * Map HTTP error codes to user-readable [AiException].
         * Error messages are scrubbed to never leak API keys.
         */
        internal fun mapHttpError(code: Int, body: String, apiKey: String): AiException {
            val safeMessage = try {
                val parsed = JSONObject(body).optJSONObject("error")?.optString("message")
                if (parsed != null) scrubSecrets(parsed, apiKey) else scrubSecrets(body.take(200), apiKey)
            } catch (_: Exception) {
                scrubSecrets(body.take(200), apiKey)
            }

            return when (code) {
                401, 403 -> AiException("API Key 无效或无权限", AiErrorType.AUTH_ERROR)
                429 -> AiException("请求过于频繁，请稍后再试", AiErrorType.RATE_LIMIT)
                in 500..599 -> AiException("服务器错误 ($code)，请稍后再试", AiErrorType.SERVER_ERROR)
                else -> AiException("请求失败 ($code): $safeMessage", AiErrorType.UNKNOWN)
            }
        }

        /**
         * Remove API keys and Bearer tokens from error messages.
         * Prevents accidental leakage of secrets into UI, logs, or crash reports.
         */
        internal fun scrubSecrets(text: String, apiKey: String): String {
            var result = text
            // Remove the specific API key
            if (apiKey.isNotBlank()) {
                result = result.replace(apiKey, "***")
            }
            // Remove Bearer tokens (sk-... or any token after "Bearer ")
            result = result.replace(Regex("Bearer\\s+sk-[a-zA-Z0-9_-]+"), "Bearer ***")
            // Remove standalone sk- keys (at least 20 chars after prefix)
            result = result.replace(Regex("sk-[a-zA-Z0-9_-]{20,}"), "***")
            return result
        }
    }

    private fun parseResponse(body: String): String {
        return try {
            val json = JSONObject(body)
            val choices = json.getJSONArray("choices")
            if (choices.length() == 0) {
                throw AiException("AI 返回了空响应", AiErrorType.EMPTY_RESPONSE)
            }
            choices.getJSONObject(0)
                .getJSONObject("message")
                .getString("content")
                .trim()
        } catch (e: AiException) {
            throw e
        } catch (e: Exception) {
            throw AiException("解析 AI 响应失败", AiErrorType.PARSE_ERROR, e)
        }
    }
}

/** Simple message for chat completion. */
data class ChatMessage(val role: String, val content: String)

/** Typed AI error with user-readable message. Never contains API Key. */
class AiException(
    message: String,
    val type: AiErrorType,
    cause: Throwable? = null
) : Exception(message, cause)

enum class AiErrorType {
    AUTH_ERROR,
    RATE_LIMIT,
    SERVER_ERROR,
    NETWORK_ERROR,
    EMPTY_RESPONSE,
    PARSE_ERROR,
    NOT_CONFIGURED,
    UNKNOWN
}
