import json
from typing import AsyncGenerator, List
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from loguru import logger
from app.core.config import settings
from app.services.prompts import get_sys_prompt

class LLMService:
    def __init__(self):
        self.llm = ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model_name=settings.MODEL_NAME,
            temperature=0.2,
            streaming=True
        )

    async def generate_response(
        self, 
        query: str, 
        context: str, 
        role: str, 
        chat_history: List[dict]
    ) -> AsyncGenerator[str, None]:
        """Generates a streaming response from Groq LLM."""
        
        # Format chat history for prompt
        history_str = "\n".join([f"{m['role']}: {m['content']}" for m in chat_history[-5:]]) if chat_history else "No previous history."
        
        # If no context provided, return the required fallback immediately
        if not context or not context.strip():
            logger.info("Empty context provided to LLMService.generate_response()")
            yield "Answer not found in uploaded documents."
            return

        # Get role-specific system prompt from consolidated prompts.py
        system_prompt = get_sys_prompt(role, context, history_str, query)

        # Prepend a strict instruction forcing the model to use ONLY the provided context
        strict_instruction = (
            "IMPORTANT: You must answer ONLY using the information in the provided Context. "
            "Do NOT use any outside knowledge. If the answer is NOT present in the Context, "
            "respond exactly with: \"Answer not found in uploaded documents.\""
        )
        system_prompt = strict_instruction + "\n\n" + system_prompt

        # Debug log: query and first 200 chars of context preview
        try:
            preview = context[:200].replace("\n", " ")
        except Exception:
            preview = ""
        logger.debug(f"LLMService Query: {query}")
        logger.debug(f"Context preview (200 chars): {preview}")
        logger.info(f"System Prompt (truncated): {system_prompt[:200]}...")

        # Prepare messages for LLM
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=query)
        ]

        try:
            full_response = "" # Keep track of full response for logging
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    full_response += chunk.content
                    yield chunk.content
            logger.info(f"LLM Response generated successfully. Length: {len(full_response)}")
        except Exception as e:
            logger.error(f"Error calling LLM: {str(e)}")
            yield f"I'm sorry, I encountered an error: {str(e)}"

llm_service = LLMService()
