"""
Content Enhancement Module: Rewriting, tone correction, and grammar checking.
Uses Gemini AI for rewriting and language-tool-python for grammar.
"""
import os
from typing import Optional

# Lazy import Gemini
_GEMINI_AVAILABLE = False
genai = None
GOOGLE_MODEL = os.environ.get("GOOGLE_MODEL", "gemini-2.5-flash")

# Lazy import language-tool
_LANGUAGETOOL_AVAILABLE = False
language_tool = None

def _ensure_gemini():
    """Lazy import of Gemini only when needed."""
    global _GEMINI_AVAILABLE, genai
    if not _GEMINI_AVAILABLE:
        try:
            import google.generativeai as genai
            _GEMINI_AVAILABLE = True
        except ImportError:
            pass
    return _GEMINI_AVAILABLE

def _ensure_languagetool():
    """Lazy import of language-tool only when needed."""
    global _LANGUAGETOOL_AVAILABLE, language_tool
    if not _LANGUAGETOOL_AVAILABLE:
        try:
            import language_tool_python
            language_tool = language_tool_python.LanguageTool('en-US')
            _LANGUAGETOOL_AVAILABLE = True
        except ImportError:
            pass
    return _LANGUAGETOOL_AVAILABLE


def rewrite_content(
    text: str,
    api_key: Optional[str] = None,
    style: str = "academic",
    max_length: Optional[int] = None
) -> Optional[str]:
    """
    Rewrite content with specified style (academic, professional, casual).
    
    Args:
        text: Text to rewrite
        api_key: Gemini API key
        style: Writing style (academic, professional, casual, concise)
        max_length: Maximum length of output (optional)
    
    Returns:
        Rewritten text or None if unavailable
    """
    if not _ensure_gemini() or not api_key or not text.strip():
        return None
    
    try:
        genai.configure(api_key=api_key)
        
        style_instructions = {
            "academic": "Rewrite in an academic, formal style suitable for research papers. Use precise terminology and maintain objectivity.",
            "professional": "Rewrite in a professional, business-appropriate style. Clear, concise, and authoritative.",
            "casual": "Rewrite in a casual, conversational style while maintaining clarity.",
            "concise": "Rewrite to be more concise and direct, removing redundancy while preserving key information."
        }
        
        instruction = style_instructions.get(style, style_instructions["academic"])
        length_note = f" Keep the output under {max_length} characters." if max_length else ""
        
        prompt = f"""{instruction}{length_note}

Original text:
{text[:4000]}

Rewritten text:"""
        
        model = genai.GenerativeModel(GOOGLE_MODEL)
        resp = model.generate_content(prompt, generation_config={"temperature": 0.4})
        rewritten = (resp.text or "").strip()
        
        if max_length and len(rewritten) > max_length:
            rewritten = rewritten[:max_length].rsplit(".", 1)[0] + "."
        
        return rewritten if rewritten else None
    except Exception as e:
        print(f"  Warning: Content rewriting failed: {e}")
        return None


def correct_tone(
    text: str,
    api_key: Optional[str] = None,
    target_tone: str = "neutral"
) -> Optional[str]:
    """
    Adjust tone of text (formal, neutral, friendly, authoritative).
    
    Args:
        text: Text to adjust
        api_key: Gemini API key
        target_tone: Desired tone (formal, neutral, friendly, authoritative)
    
    Returns:
        Text with adjusted tone or None if unavailable
    """
    if not _ensure_gemini() or not api_key or not text.strip():
        return None
    
    try:
        genai.configure(api_key=api_key)
        
        tone_instructions = {
            "formal": "Make the tone more formal and respectful. Use formal language and avoid contractions.",
            "neutral": "Make the tone neutral and objective. Remove emotional language.",
            "friendly": "Make the tone more friendly and approachable while maintaining professionalism.",
            "authoritative": "Make the tone more authoritative and confident. Use assertive language."
        }
        
        instruction = tone_instructions.get(target_tone, tone_instructions["neutral"])
        
        prompt = f"""Adjust the tone of the following text. {instruction}

Original text:
{text[:3000]}

Adjusted text:"""
        
        model = genai.GenerativeModel(GOOGLE_MODEL)
        resp = model.generate_content(prompt, generation_config={"temperature": 0.3})
        adjusted = (resp.text or "").strip()
        
        return adjusted if adjusted else None
    except Exception as e:
        print(f"  Warning: Tone correction failed: {e}")
        return None


def check_grammar(text: str) -> dict:
    """
    Check grammar and spelling using language-tool.
    
    Args:
        text: Text to check
    
    Returns:
        Dictionary with:
        - errors: List of grammar/spelling errors
        - corrected_text: Text with corrections applied
        - error_count: Number of errors found
    """
    if not _ensure_languagetool():
        return {
            "errors": [],
            "corrected_text": text,
            "error_count": 0,
            "available": False
        }
    
    try:
        matches = language_tool.check(text)
        
        errors = []
        for match in matches:
            errors.append({
                "message": match.message,
                "replacements": match.replacements[:5],  # Top 5 suggestions
                "offset": match.offset,
                "length": match.errorLength,
                "rule": match.ruleId
            })
        
        # Apply corrections
        corrected_text = language_tool.correct(text)
        
        return {
            "errors": errors,
            "corrected_text": corrected_text,
            "error_count": len(errors),
            "available": True
        }
    except Exception as e:
        print(f"  Warning: Grammar check failed: {e}")
        return {
            "errors": [],
            "corrected_text": text,
            "error_count": 0,
            "available": False
        }


def enhance_content(
    text: str,
    api_key: Optional[str] = None,
    rewrite: bool = False,
    rewrite_style: str = "academic",
    correct_tone_flag: bool = False,
    target_tone: str = "neutral",
    check_grammar_flag: bool = True
) -> dict:
    """
    Comprehensive content enhancement pipeline.
    
    Args:
        text: Original text
        api_key: Gemini API key
        rewrite: Whether to rewrite content
        rewrite_style: Style for rewriting
        correct_tone_flag: Whether to adjust tone
        target_tone: Target tone
        check_grammar_flag: Whether to check grammar
    
    Returns:
        Dictionary with:
        - original: Original text
        - enhanced: Enhanced text
        - grammar: Grammar check results
        - steps_applied: List of steps applied
    """
    result = {
        "original": text,
        "enhanced": text,
        "grammar": None,
        "steps_applied": []
    }
    
    current_text = text
    
    # Step 1: Grammar check
    if check_grammar_flag:
        grammar_result = check_grammar(current_text)
        result["grammar"] = grammar_result
        if grammar_result["available"] and grammar_result["error_count"] > 0:
            current_text = grammar_result["corrected_text"]
            result["steps_applied"].append("grammar_correction")
    
    # Step 2: Tone correction
    if correct_tone_flag and api_key:
        tone_adjusted = correct_tone(current_text, api_key, target_tone)
        if tone_adjusted:
            current_text = tone_adjusted
            result["steps_applied"].append(f"tone_adjustment_{target_tone}")
    
    # Step 3: Rewriting
    if rewrite and api_key:
        rewritten = rewrite_content(current_text, api_key, rewrite_style)
        if rewritten:
            current_text = rewritten
            result["steps_applied"].append(f"rewriting_{rewrite_style}")
    
    result["enhanced"] = current_text
    return result
