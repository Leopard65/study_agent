package com.example.mathagent

import com.example.mathagent.data.ai.AiErrorType
import com.example.mathagent.data.ai.AiException
import com.example.mathagent.data.ai.ChatMessage
import com.example.mathagent.data.ai.OpenAiApi
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Unit tests for OpenAiApi using MockWebServer.
 * Covers: request path, JSON structure, auth header,
 * HTTP error mapping, parse errors, and secret scrubbing.
 */
class OpenAiApiTest {

    private lateinit var server: MockWebServer

    @Before
    fun setup() {
        server = MockWebServer()
        server.start()
    }

    @After
    fun teardown() {
        server.shutdown()
    }

    private fun baseUrl(): String = server.url("/v1").toString().trimEnd('/')

    private fun enqueueSuccess(content: String = "Hello from AI") {
        val json = """
        {
          "choices": [
            {
              "message": {
                "role": "assistant",
                "content": "$content"
              }
            }
          ]
        }
        """.trimIndent()
        server.enqueue(MockResponse().setBody(json).setHeader("Content-Type", "application/json"))
    }

    private fun enqueueError(code: Int, body: String) {
        server.enqueue(
            MockResponse()
                .setResponseCode(code)
                .setBody(body)
                .setHeader("Content-Type", "application/json")
        )
    }

    private fun buildApi(
        baseUrl: String = baseUrl(),
        apiKey: String = "sk-test-key-1234567890abcdef",
        model: String = "gpt-4o-mini"
    ) = OpenAiApi(baseUrl = baseUrl, apiKey = apiKey, model = model)

    // ---- Request path ----

    @Test
    fun chatCompletion_usesCorrectPath() = runTest {
        enqueueSuccess()
        val api = buildApi()
        api.chatCompletion(listOf(ChatMessage("user", "hi")))

        val request = server.takeRequest()
        assertEquals("/v1/chat/completions", request.path)
    }

    @Test
    fun chatCompletion_baseUrlAlreadyHasChatCompletions_noDoublePath() = runTest {
        enqueueSuccess()
        val api = buildApi(baseUrl = "${baseUrl()}/chat/completions")
        api.chatCompletion(listOf(ChatMessage("user", "hi")))

        val request = server.takeRequest()
        assertEquals("/v1/chat/completions", request.path)
    }

    // ---- Request JSON structure ----

    @Test
    fun chatCompletion_requestJsonContainsRequiredFields() = runTest {
        enqueueSuccess()
        val api = buildApi(model = "gpt-4")
        api.chatCompletion(listOf(
            ChatMessage("system", "You are a tutor"),
            ChatMessage("user", "Explain 1+1")
        ))

        val request = server.takeRequest()
        val body = request.body.readUtf8()

        assertTrue("Should contain model", body.contains("\"model\":\"gpt-4\""))
        assertTrue("Should contain messages", body.contains("\"messages\""))
        assertTrue("Should contain temperature", body.contains("\"temperature\""))
        assertTrue("Should contain max_tokens", body.contains("\"max_tokens\""))
        assertTrue("Should contain system role", body.contains("\"role\":\"system\""))
        assertTrue("Should contain user role", body.contains("\"role\":\"user\""))
        assertTrue("Should contain content", body.contains("Explain 1+1"))
    }

    // ---- Authorization header ----

    @Test
    fun chatCompletion_authorizationHeaderPresent() = runTest {
        enqueueSuccess()
        val apiKey = "sk-test-authorization-key"
        val api = buildApi(apiKey = apiKey)
        api.chatCompletion(listOf(ChatMessage("user", "hi")))

        val request = server.takeRequest()
        assertEquals("Bearer $apiKey", request.getHeader("Authorization"))
    }

    // ---- Successful response ----

    @Test
    fun chatCompletion_success_returnsContent() = runTest {
        enqueueSuccess("The answer is 42")
        val api = buildApi()
        val result = api.chatCompletion(listOf(ChatMessage("user", "what?")))
        assertEquals("The answer is 42", result)
    }

    // ---- HTTP error mapping ----

    @Test
    fun chatCompletion_401_mapsToAuthError() = runTest {
        enqueueError(401, """{"error":{"message":"Invalid API key"}}""")
        val api = buildApi()
        try {
            api.chatCompletion(listOf(ChatMessage("user", "hi")))
            assertTrue("Should throw", false)
        } catch (e: AiException) {
            assertEquals(AiErrorType.AUTH_ERROR, e.type)
            assertFalse("Message should not contain API key", e.message!!.contains("sk-"))
        }
    }

    @Test
    fun chatCompletion_403_mapsToAuthError() = runTest {
        enqueueError(403, """{"error":{"message":"Forbidden"}}""")
        val api = buildApi()
        try {
            api.chatCompletion(listOf(ChatMessage("user", "hi")))
            assertTrue("Should throw", false)
        } catch (e: AiException) {
            assertEquals(AiErrorType.AUTH_ERROR, e.type)
        }
    }

    @Test
    fun chatCompletion_429_mapsToRateLimit() = runTest {
        enqueueError(429, """{"error":{"message":"Rate limit exceeded"}}""")
        val api = buildApi()
        try {
            api.chatCompletion(listOf(ChatMessage("user", "hi")))
            assertTrue("Should throw", false)
        } catch (e: AiException) {
            assertEquals(AiErrorType.RATE_LIMIT, e.type)
        }
    }

    @Test
    fun chatCompletion_500_mapsToServerError() = runTest {
        enqueueError(500, """{"error":{"message":"Internal error"}}""")
        val api = buildApi()
        try {
            api.chatCompletion(listOf(ChatMessage("user", "hi")))
            assertTrue("Should throw", false)
        } catch (e: AiException) {
            assertEquals(AiErrorType.SERVER_ERROR, e.type)
            assertTrue(e.message!!.contains("500"))
        }
    }

    @Test
    fun chatCompletion_503_mapsToServerError() = runTest {
        enqueueError(503, """{"error":{"message":"Service unavailable"}}""")
        val api = buildApi()
        try {
            api.chatCompletion(listOf(ChatMessage("user", "hi")))
            assertTrue("Should throw", false)
        } catch (e: AiException) {
            assertEquals(AiErrorType.SERVER_ERROR, e.type)
        }
    }

    @Test
    fun chatCompletion_418_mapsToUnknown() = runTest {
        enqueueError(418, "I'm a teapot")
        val api = buildApi()
        try {
            api.chatCompletion(listOf(ChatMessage("user", "hi")))
            assertTrue("Should throw", false)
        } catch (e: AiException) {
            assertEquals(AiErrorType.UNKNOWN, e.type)
            assertTrue(e.message!!.contains("418"))
        }
    }

    // ---- Parse error ----

    @Test
    fun chatCompletion_invalidJson_mapsToParseError() = runTest {
        server.enqueue(MockResponse().setBody("not json at all"))
        val api = buildApi()
        try {
            api.chatCompletion(listOf(ChatMessage("user", "hi")))
            assertTrue("Should throw", false)
        } catch (e: AiException) {
            assertEquals(AiErrorType.PARSE_ERROR, e.type)
        }
    }

    @Test
    fun chatCompletion_emptyChoices_mapsToEmptyResponse() = runTest {
        server.enqueue(MockResponse().setBody("""{"choices":[]}"""))
        val api = buildApi()
        try {
            api.chatCompletion(listOf(ChatMessage("user", "hi")))
            assertTrue("Should throw", false)
        } catch (e: AiException) {
            assertEquals(AiErrorType.EMPTY_RESPONSE, e.type)
        }
    }

    // ---- Secret scrubbing ----

    @Test
    fun scrubSecrets_removesSpecificApiKey() {
        val key = "sk-abc123def456ghi789jkl012mno"
        val text = "Error with key $key in response"
        val scrubbed = OpenAiApi.scrubSecrets(text, key)
        assertFalse("Should not contain the API key", scrubbed.contains(key))
        assertTrue("Should contain placeholder", scrubbed.contains("***"))
    }

    @Test
    fun scrubSecrets_removesBearerToken() {
        val text = "Authorization: Bearer sk-abc123def456ghi789jkl012mno failed"
        val scrubbed = OpenAiApi.scrubSecrets(text, "some-other-key")
        assertFalse("Should not contain sk- token", scrubbed.contains("sk-abc123"))
        assertTrue("Should contain placeholder", scrubbed.contains("***"))
    }

    @Test
    fun scrubSecrets_removesStandaloneSkKeys() {
        val text = "Invalid key sk-abcdefghijklmnopqrstuvwxyz provided"
        val scrubbed = OpenAiApi.scrubSecrets(text, "")
        assertFalse("Should not contain sk- key", scrubbed.contains("sk-abcdefghij"))
    }

    @Test
    fun mapHttpError_bodyContainsApiKey_scrubbedFromMessage() {
        val key = "sk-leaked-key-1234567890abcdef"
        val body = """{"error":{"message":"Invalid key: $key"}}"""
        val ex = OpenAiApi.mapHttpError(401, body, key)
        assertFalse("AiException message should not contain API key", ex.message!!.contains(key))
        assertFalse("AiException message should not contain sk- pattern", ex.message!!.contains("sk-leaked"))
    }

    @Test
    fun mapHttpError_rawBodyContainsApiKey_scrubbedFromMessage() {
        val key = "sk-body-leak-1234567890abcdef"
        val body = "Error: authentication failed for key $key"
        val ex = OpenAiApi.mapHttpError(400, body, key)
        assertFalse("Should not leak API key in message", ex.message!!.contains(key))
    }

    @Test
    fun mapHttpError_normalError_noSkKey() {
        val body = """{"error":{"message":"Rate limit exceeded"}}"""
        val ex = OpenAiApi.mapHttpError(429, body, "sk-normal-key-1234567890")
        assertEquals(AiErrorType.RATE_LIMIT, ex.type)
        assertFalse("Should not contain sk- key", ex.message!!.contains("sk-"))
    }
}
