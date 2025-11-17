#!/usr/bin/env python3
"""Quick test to verify chat feature setup."""

import sys

def test_imports():
    """Test that all chat modules can be imported."""
    print("Testing imports...")

    try:
        from backend.app.chat.intent_extractor import extract_intent_from_conversation
        print("✓ Intent extractor imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import intent extractor: {e}")
        return False

    try:
        from backend.app.chat.edit_parser import parse_edit_request
        print("✓ Edit parser imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import edit parser: {e}")
        return False

    try:
        from backend.app.api.chat import router
        print("✓ Chat API router imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import chat router: {e}")
        return False

    try:
        from backend.app.main import app
        print("✓ Main app with chat router imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import main app: {e}")
        return False

    return True


def test_config():
    """Test that config has OpenAI settings."""
    print("\nTesting configuration...")

    try:
        from backend.app.config import get_settings
        settings = get_settings()

        if hasattr(settings, 'openai_api_key'):
            print("✓ OpenAI API key configured")
        else:
            print("✗ OpenAI API key not in settings")
            return False

        if hasattr(settings, 'openai_model'):
            print(f"✓ OpenAI model configured: {settings.openai_model}")
        else:
            print("✗ OpenAI model not in settings")
            return False

        return True
    except Exception as e:
        print(f"✗ Failed to load config: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Chat Feature Setup Verification")
    print("=" * 60)

    imports_ok = test_imports()
    config_ok = test_config()

    print("\n" + "=" * 60)
    if imports_ok and config_ok:
        print("✅ All checks passed! Chat feature is ready.")
        print("\nNext steps:")
        print("1. Set OPENAI_API_KEY in your .env file")
        print("2. Start backend: uvicorn backend.app.main:app --reload")
        print("3. Start frontend: streamlit run frontend/app.py")
        print("4. Navigate to 'Chat Plan' page")
        return 0
    else:
        print("❌ Some checks failed. Please review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
