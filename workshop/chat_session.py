import logging
from .conversation_history_manager import estimate_conversation_tokens, summarize_conversation

TOKEN_LIMIT = 3500

class BaseChatSession:
    def __init__(self, mode, messages, context_panel, prompt_panel, embedding_index):
        self.mode = mode
        self.messages = messages
        self.context_panel = context_panel
        self.prompt_panel = prompt_panel
        self.embedding_index = embedding_index

    def validate(self) -> bool:
        return True

    def get_system_prompt(self, prompt_config, compendium_text, story_text):
        """Returns the base system instructions."""
        return prompt_config.get("text", "")

    def augment_user_message(self, user_input, story_text, retrieved_context, compendium_text=None):
        """
        Wraps context in XML-style tags. This helps the LLM distinguish 
        between reference facts and the user's actual command.
        """
        parts = []
        
        # 1. Add Compendium Data (if not already in system prompt)
        if compendium_text:
            parts.append(f"<compendium>\n{compendium_text}\n</compendium>")
            
        # 2. Add Story Context (the manuscript/text)
        if story_text:
            parts.append(f"<story_context>\n{story_text}\n</story_context>")
            
        # 3. Add RAG/Vector search results
        if retrieved_context:
            parts.append(f"<retrieved_knowledge>\n" + "\n".join(retrieved_context) + "\n</retrieved_knowledge>")
            
        # 4. Add the actual user input at the end
        parts.append(f"User Request: {user_input}")
        
        return "\n\n".join(parts)

    def construct_message(self, user_input):
        if not user_input:
            return None
            
        prompt_config = self.prompt_panel.get_prompt()
        overrides = self.prompt_panel.get_overrides() if prompt_config else {}
        
        compendium_text = self.context_panel.get_selected_compendium_text()
        story_text = self.context_panel.get_selected_story_text()
        
        # Determine if compendium goes in System or User
        # We'll pass None to augment if the subclass already handled it in System
        sys_compendium = compendium_text if self.mode == "Role Play" else None
        user_compendium = compendium_text if self.mode == "Writing Coach" else None

        system_prompt = self.get_system_prompt(prompt_config, sys_compendium, story_text)
        retrieved_context = self.embedding_index.query(user_input)
        
        augmented_message = self.augment_user_message(
            user_input, story_text, retrieved_context, compendium_text=user_compendium
        )
        
        payload = list(self.messages)
        payload.append({"role": "system", "content": system_prompt})
        payload.append({"role": "user", "content": augmented_message})
        
        if estimate_conversation_tokens(payload) > TOKEN_LIMIT:
            # Keep last 2 messages from history + current user message out of summarization
            history_to_summarize = payload[:-4] if len(payload) > 4 else []
            summary = summarize_conversation(history_to_summarize, overrides=overrides)

            # Rebuild payload with summary + fresh user input
            payload = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"""[Conversation Summary]\n{summary}\n\n[Recent Context]\n{self._format_last_messages(payload[-4:-2]) if len(payload) > 3 else ""}\n\n{augmented_message}"""}
            ]
        
        logging.debug(f"Constructed payload: {len(payload)} messages")
        return payload

    def _format_last_messages(self, messages):
        formatted = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            formatted.append(f"{role.upper()}: {content}")
        return "\n".join(formatted)

    def append_message(self, role, content):
        self.messages.append({"role": role, "content": content})

    def get_preview_payload(self, view):
        user_input = view.chat_input.toPlainText().strip()
        return self.construct_message(user_input)

    def mark_last_exchange_as_edited(self):
        messages = self.messages
        if len(messages) >= 2 and messages[-2].get("role") == "user":
            messages[-2]["edited"] = True
            if len(messages) > 2 and messages[-1].get("role") == "assistant":
                messages[-1]["edited"] = True

class WritingCoachSession(BaseChatSession):
    def __init__(self, messages, context_panel, prompt_panel, embedding_index):
        super().__init__("Writing Coach", messages, context_panel, prompt_panel, embedding_index)
    # Uses default logic: Compendium goes into the User Message via XML tags

class RolePlaySession(BaseChatSession):
    def __init__(self, messages, context_panel, prompt_panel, embedding_index):
        super().__init__("Role Play", messages, context_panel, prompt_panel, embedding_index)

    def validate(self) -> bool:
        return bool(self.context_panel.get_selected_compendium_text())

    def get_system_prompt(self, prompt_config, compendium_text, story_text):
        """
        In Role Play, character details are part of the 'identity',
        so we wrap them in XML inside the System Prompt.
        """
        base_prompt = super().get_system_prompt(prompt_config, compendium_text, story_text)
        
        char_context = (
            f"\n\n<compendium_character_profile>\n{compendium_text}\n"
            f"</compendium_character_profile>\n"
            f"Please stay in character based on the profile above."
        )
        return base_prompt + char_context