from pathlib import Path
from fastapi import APIRouter, Body
from third_party.Botok.botok import Text, sentence_tokenizer, WordTokenizer,Config

router = APIRouter()

# Initialize WordTokenizer once at module load (not on every request)
_word_tokenizer = None

def get_word_tokenizer():
    """Lazy initialization of WordTokenizer - downloads dialect pack once."""
    global _word_tokenizer
    
    out_dir = Path("/tmp") / "dialects"
    out_dir.mkdir(exist_ok=True, parents=True)
    if _word_tokenizer is None:
        _word_tokenizer = WordTokenizer(config=Config(dialect_name="general",base_path=out_dir))
    return _word_tokenizer


def sent_tok(raw):
    w = get_word_tokenizer()  # Reuse the singleton instance
    tokens = w.tokenize(raw, spaces_as_punct=True)
    return sentence_tokenizer(tokens)


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


def sentence_segmentation(text: str) -> str:
    t = Text(text).custom_pipeline("basic_cleanup", sent_tok, "dummy", plaintext_sent_par)
    return t


@router.post("/tokenizer/sentence_segmentation", response_model=str)
def sentence_segmentation_endpoint(text: str = Body(..., embed=True)) -> str:
    """Perform sentence segmentation on Tibetan text."""
    text = text.strip().replace("\n", "")
    return sentence_segmentation(text)