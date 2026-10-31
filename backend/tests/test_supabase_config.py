import base64
import json
import os
import unittest

from app.services.supabase_service import is_supabase_configured


def _decode_supabase_role_key(key: str):
    parts = key.split('.')
    if len(parts) < 2:
        return None
    payload = parts[1]
    payload += '=' * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload.encode()).decode())


class SupabaseConfigTests(unittest.TestCase):
    def test_supabase_service_role_key_is_not_anon(self):
        key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or ''
        self.assertTrue(key, 'SUPABASE_SERVICE_ROLE_KEY is missing in the environment')
        payload = _decode_supabase_role_key(key)
        self.assertEqual(payload.get('role'), 'service_role', (
            'Supabase key is not a service_role token. The active role is '
            f'{payload.get("role")} and backend uploads will fail.'
        ))

    def test_supabase_config_is_enabled_only_for_valid_service_role(self):
        self.assertTrue(is_supabase_configured())


if __name__ == '__main__':
    unittest.main()
