from odoo import models, api
import requests
import json
import logging

_logger = logging.getLogger(__name__)

class OpenAIService(models.AbstractModel):
    _name = 'openai.service'
    _description = 'OpenAI Service Helper'

    def _get_api_key(self):
        key = self.env['ir.config_parameter'].sudo().get_param('du_an.openai_api_key')
        if not key:
            try:
                import os
                key = os.environ.get('OPENAI_API_KEY')
                if not key:
                    from os.path import join, dirname
                    dotenv_path = join(dirname(dirname(dirname(dirname(__file__)))), '.env')
                    if os.path.exists(dotenv_path):
                        with open(dotenv_path) as f:
                            for line in f:
                                if line.startswith('OPENAI_API_KEY='):
                                    key = line.strip().split('=', 1)[1]
                                    break
            except Exception:
                pass
        return key

    def get_chat_completion(self, prompt, system_prompt="You are a helpful assistant.", model="gpt-4o-mini"):
        api_key = self._get_api_key()
        if not api_key:
            _logger.warning("OpenAI API Key not found in System Parameters or .env")
            return None
            
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions", 
                headers=headers, 
                json=payload, 
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content']
        except Exception as e:
            _logger.error(f"OpenAI API Error: {str(e)}")
            return None
