from typing import List, Dict, Optional
import requests
from datetime import datetime
import json
import hmac
import hashlib
import base64
from config.settings import settings

class VolcengineLLM:
    def __init__(self):
        self.api_key = settings.VOLCENGINE_API_KEY
        self.api_secret = settings.VOLCENGINE_API_SECRET
        self.base_url = "https://open.volcengineapi.com"
        self.api_version = "2024-01-01"  # Update as needed
        
    def _generate_signature(self, method: str, path: str, params: Dict) -> str:
        """Generate signature for Volcengine API authentication."""
        timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        string_to_sign = f"{method}\n{path}\n{timestamp}\n{json.dumps(params, sort_keys=True)}"
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        return base64.b64encode(signature).decode('utf-8')
    
    def _make_request(self, endpoint: str, payload: Dict) -> Dict:
        """Make authenticated request to Volcengine API."""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"HMAC-SHA256 {self._generate_signature('POST', endpoint, payload)}",
            "Content-Type": "application/json",
            "X-Date": datetime.utcnow().strftime('%Y%m%dT%H%M%SZ'),
            "X-Api-Key": self.api_key,
            "X-Api-Version": self.api_version
        }
        
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        top_p: float = None
    ) -> Dict:
        """Generate chat completion using Volcengine API."""
        endpoint = "/v1/chat/completions"
        
        payload = {
            "messages": messages,
            "temperature": temperature or settings.TEMPERATURE,
            "max_tokens": max_tokens or settings.MAX_TOKENS,
            "top_p": top_p or settings.TOP_P
        }
        
        return self._make_request(endpoint, payload)
    
    def summarize_text(self, text: str, max_length: int = 500) -> str:
        """Summarize text using Volcengine API."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant that summarizes text concisely."},
            {"role": "user", "content": f"Please summarize the following text in about {max_length} characters:\n\n{text}"}
        ]
        
        response = self.chat_completion(messages, temperature=0.3)
        return response["choices"][0]["message"]["content"]
    
    def extract_world_knowledge(self, text: str) -> Dict:
        """Extract structured world knowledge from text."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant that extracts structured information about characters, locations, and events from text."},
            {"role": "user", "content": f"Please analyze this text and extract key information about characters, locations, and events in a structured format:\n\n{text}"}
        ]
        
        response = self.chat_completion(messages, temperature=0.2)
        # Parse the response into structured data
        try:
            return json.loads(response["choices"][0]["message"]["content"])
        except json.JSONDecodeError:
            return {
                "characters": [],
                "locations": [],
                "events": []
            }
    
    def generate_character_response(
        self,
        character_info: Dict,
        context: str,
        user_input: str,
        dialogue_history: List[Dict]
    ) -> str:
        """Generate in-character response based on character info and context."""
        system_prompt = f"""You are role-playing as {character_info['name']}.
Character traits: {', '.join(character_info['traits'])}
Background: {character_info['background']}
Current context: {context}

Respond in character, maintaining consistency with the character's personality and knowledge."""
        
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add dialogue history
        for entry in dialogue_history[-5:]:  # Last 5 turns
            messages.append({"role": "user" if entry["is_user"] else "assistant", "content": entry["text"]})
        
        # Add current user input
        messages.append({"role": "user", "content": user_input})
        
        response = self.chat_completion(messages)
        return response["choices"][0]["message"]["content"] 