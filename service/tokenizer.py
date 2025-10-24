from typing import List
from third_party.Botok.botok import Text, sentence_tokenizer, WordTokenizer,Config
import os
import tempfile
from pathlib import Path


def get_writable_base_path():
    base_path = 'data/'
    return base_path







def sent_tok(raw):
    
    config = Config(dialect_name="general")
    w = WordTokenizer(config=config)
    tokens = w.tokenize(raw, spaces_as_punct=True)
    return sentence_tokenizer(tokens)


def word_tok(raw):
    
    
    config = Config(dialect_name="general")
    w = WordTokenizer(config=config)
    lines = raw.split("\n")
    segmented = []
    for l in lines:
        seg = w.tokenize(l)

        for token in seg:
            segmented.append(token.text)
    return segmented

def join_short_segments(segments: List[str], max_length: int = 100) -> List[str]:
    joined_segments = []
    buffer = ""
    
    for segment in segments:
        if len(buffer) + len(segment) <= max_length:
            # Add to buffer if within limit
            buffer += (" " if buffer else "") + segment
        else:
            # Append buffer to result and start a new one
            if buffer:
                joined_segments.append(buffer)
            buffer = segment
    
    # Append any remaining buffer content
    if buffer:
        joined_segments.append(buffer)
    
    return joined_segments


def plaintext_sent_par(units, sep="\n") -> str:
    out = []
    for u in units:
        unit = "".join([word.text for word in u['tokens']]).strip()
        while out and unit and len(units) >= 2 and (unit[0] == " " or unit[0] == "།"):
            out[-1] += unit[0]
            if len(unit) >= 2:
                unit = unit[1:]
            else:
                unit = ""
        out.append(unit)
    return sep.join(out)

def segment_text(text: str, max_length: int = 100, lang: str = '') -> List[str]:
    segments = []
    if lang == 'bo':
        sentences = Text(tibetan_text_cleanup(text)).custom_pipeline("basic_cleanup", sent_tok, "dummy", plaintext_sent_par)
        lines = sentences.strip().splitlines()
    else:
        lines=tokenize_sentences_spacy(text)

    segments=join_short_segments(lines,max_length=max_length)
    return segments

def get_word_count(text: str, lang: str = '') -> int:
    if lang == 'bo':
        return len(word_tok(text))
    else:
        return len(tokenize_words_spacy(text))
    

def tibetan_text_cleanup(text: str) -> str:
    return text.replace(" ", " ").replace("​", " ").replace("། ། ", "། །")