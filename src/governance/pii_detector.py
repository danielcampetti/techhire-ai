"""PII detection and masking for Brazilian financial data (LGPD compliance).

Detects and masks CPF numbers, personal names, high-value monetary amounts,
phone numbers, and email addresses in free-form text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

MONEY_THRESHOLD = 10_000.0


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PIIType(Enum):
    """Category of personally-identifiable information."""
    CPF = "cpf"
    NAME = "name"
    MONEY = "money"
    PHONE = "phone"
    EMAIL = "email"


class MaskLevel(Enum):
    """How aggressively to mask detected PII."""
    PARTIAL = "partial"
    FULL = "full"


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class PIIMatch:
    """A single PII occurrence found in text.

    Attributes:
        type: Category of PII.
        original: The verbatim substring that was detected.
        start: Start character offset in the source text.
        end: End character offset (exclusive) in the source text.
        masked_partial: Partially-obfuscated form (e.g. initials, first digit group).
        masked_full: Fully-opaque replacement token.
    """
    type: PIIType
    original: str
    start: int
    end: int
    masked_partial: str
    masked_full: str


# ---------------------------------------------------------------------------
# Brazilian name lists
# ---------------------------------------------------------------------------

_BRAZILIAN_NAMES = {
    "Ana", "Maria", "José", "João", "Pedro", "Paulo", "Carlos", "Luis", "Lucas",
    "Gabriel", "Rafael", "Daniel", "Felipe", "Bruno", "Marcos", "Eduardo", "Ricardo",
    "Fernando", "Diego", "Rodrigo", "Gustavo", "Thiago", "Alexandre", "Marcelo",
    "Anderson", "Leandro", "Leonardo", "Mateus", "Vinicius", "Igor", "Renato",
    "Caio", "Murilo", "Henrique", "Arthur", "Samuel", "Enzo", "Nicolas", "Davi",
    "Levi", "Cauã", "Lorenzo", "Miguel", "Bernardo", "Heitor", "Theo", "Ravi",
    "Gael", "Bento", "Luca", "Francisca", "Antônia", "Adriana", "Juliana",
    "Mariana", "Camila", "Aline", "Amanda", "Bruna", "Carla", "Cristiane",
    "Daniela", "Elaine", "Fernanda", "Gabriela", "Helena", "Isabela", "Jéssica",
    "Larissa", "Letícia", "Luana", "Luciana", "Manuela", "Natalia", "Patricia",
    "Priscila", "Rafaela", "Renata", "Sandra", "Simone", "Tatiane", "Thais",
    "Vanessa", "Viviane", "Beatriz", "Carolina", "Vitória", "Sophia", "Alice",
    "Laura", "Valentina", "Livia", "Yasmin", "Isadora", "Clara", "Lara",
    "Giovanna", "Julia", "Eduarda", "Luisa", "Rebeca", "Cecilia", "Melissa",
}

_NAME_EXCLUSIONS = {
    # Regulatory / institutional
    "Art", "Resolução", "Circular", "COAF", "Banco", "Central", "LGPD", "CLT",
    "PIX", "STR", "RSFN", "BCB", "CMN", "CVM", "SPB", "BACEN", "Lei", "Decreto",
    "Portaria", "Instrução", "Normativa", "Complementar", "Federal", "Brasil",
    "Brazilian", "Capítulo", "Seção", "Parágrafo",
    # Common Portuguese nouns / adjectives that appear in Title-Case context
    "Cliente", "Clientes", "Transação", "Transações", "Depósito", "Depósitos",
    "Conta", "Contas", "Valor", "Valores", "Relatório", "Relatórios",
    "Alerta", "Alertas", "Sistema", "Sistemas", "Operação", "Operações",
    "Processo", "Processos", "Empresa", "Empresas", "Entidade", "Entidades",
    "Agência", "Agências", "Conformidade", "Compliance", "Produto", "Produtos",
    "Serviço", "Serviços", "Contrato", "Contratos", "Pessoa", "Pessoas",
}


# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

_RE_CPF = re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b')

_RE_EMAIL = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')

_RE_PHONE = re.compile(r'(?<!\d)\(?\d{2}\)?\s*\d{4,5}-?\d{4}(?!\d)')

_RE_MONEY = re.compile(r'R\$\s*[\d.,]+')

# Multi-word name: 2+ consecutive Title-Case words (allowing accented chars)
_UC = r'[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÇÜ]'
_LC = r'[a-záéíóúâêîôûãõàçü]'
_WORD = rf'{_UC}{_LC}+'
_RE_MULTIWORD_NAME = re.compile(rf'(?<!\w){_WORD}(?:\s+{_WORD})+(?!\w)')

# Single Title-Case word (for known Brazilian first names)
_RE_SINGLE_WORD = re.compile(rf'(?<!\w){_UC}{_LC}+(?!\w)')


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_money_value(raw: str) -> float:
    """Extract numeric value from 'R$ 50.000,00' or 'R$50000'.

    Args:
        raw: Raw money string starting with 'R$'.

    Returns:
        Float value, or 0.0 if parsing fails.
    """
    digits = raw.replace("R$", "").replace(" ", "").strip()
    if "," in digits:
        digits = digits.replace(".", "").replace(",", ".")
    else:
        digits = digits.replace(".", "")
    try:
        return float(digits)
    except ValueError:
        return 0.0


def _mask_cpf_partial(original: str) -> str:
    """Return partially-masked CPF: '123.***.**9-09'.

    Args:
        original: The CPF string as found in text.

    Returns:
        Partially-masked CPF string.
    """
    digits = re.sub(r'\D', '', original)
    if len(digits) != 11:
        return "[CPF_MASCARADO]"
    return f"{digits[:3]}.***.**{digits[8]}-{digits[9:]}"


def _mask_name_partial(original: str) -> str:
    """Return initials form of a name: 'Roberto Alves Costa' → 'R. A. C.'.

    Args:
        original: Full name string.

    Returns:
        Initials string.
    """
    parts = original.split()
    return " ".join(p[0] + "." for p in parts)


def _mask_phone_partial(original: str) -> str:
    """Return partially-masked phone: '(11) ****-1234'.

    Args:
        original: Phone number string as found in text.

    Returns:
        Partially-masked phone string.
    """
    digits = re.sub(r'\D', '', original)
    last4 = digits[-4:]
    if original.startswith("("):
        area = digits[:2]
        return f"({area}) ****-{last4}"
    return f"****-{last4}"


def _mask_email_partial(original: str) -> str:
    """Return partially-masked email: 'joao@email.com' → 'j***@email.com'.

    Args:
        original: Email address string.

    Returns:
        Partially-masked email string.
    """
    if "@" not in original:
        return "[EMAIL_MASCARADO]"
    user, domain = original.split("@", 1)
    return f"{user[0]}***@{domain}"


def _remove_overlaps(matches: list[PIIMatch]) -> list[PIIMatch]:
    """Keep the longer match when two matches overlap in the source text.

    Args:
        matches: Unsorted list of PIIMatch objects.

    Returns:
        Deduplicated list with no overlapping spans.
    """
    if not matches:
        return matches
    sorted_m = sorted(matches, key=lambda m: (m.start, -(m.end - m.start)))
    result = [sorted_m[0]]
    for current in sorted_m[1:]:
        last = result[-1]
        if current.start < last.end:  # overlap
            if (current.end - current.start) > (last.end - last.start):
                result[-1] = current
            # else keep last (already longer or equal)
        else:
            result.append(current)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_pii(text: str) -> list[PIIMatch]:
    """Detect all PII occurrences in *text*.

    Detection order: CPF → Email → Phone → Money → Names.
    Overlapping matches are resolved by keeping the longer span.

    Args:
        text: Input text to scan.

    Returns:
        List of PIIMatch objects, sorted by start position.
    """
    matches: list[PIIMatch] = []

    # 1. CPF
    for m in _RE_CPF.finditer(text):
        original = m.group()
        matches.append(PIIMatch(
            type=PIIType.CPF,
            original=original,
            start=m.start(),
            end=m.end(),
            masked_partial=_mask_cpf_partial(original),
            masked_full="[CPF_MASCARADO]",
        ))

    # 2. Email (before phone — emails can contain digit sequences)
    for m in _RE_EMAIL.finditer(text):
        original = m.group()
        matches.append(PIIMatch(
            type=PIIType.EMAIL,
            original=original,
            start=m.start(),
            end=m.end(),
            masked_partial=_mask_email_partial(original),
            masked_full="[EMAIL_MASCARADO]",
        ))

    # 3. Phone
    for m in _RE_PHONE.finditer(text):
        original = m.group()
        matches.append(PIIMatch(
            type=PIIType.PHONE,
            original=original,
            start=m.start(),
            end=m.end(),
            masked_partial=_mask_phone_partial(original),
            masked_full="[TELEFONE_MASCARADO]",
        ))

    # 4. Money (only if ≥ threshold)
    for m in _RE_MONEY.finditer(text):
        original = m.group()
        if _parse_money_value(original) >= MONEY_THRESHOLD:
            matches.append(PIIMatch(
                type=PIIType.MONEY,
                original=original,
                start=m.start(),
                end=m.end(),
                masked_partial="R$ *.**",
                masked_full="[VALOR_MASCARADO]",
            ))

    # 5a. Multi-word names
    already_covered: set[tuple[int, int]] = set()
    for m in _RE_MULTIWORD_NAME.finditer(text):
        original = m.group()
        words = original.split()
        # Skip if ALL words are in exclusions
        if all(w in _NAME_EXCLUSIONS for w in words):
            continue
        # Trim leading and trailing exclusion words to isolate the name core
        start_idx = 0
        while start_idx < len(words) and words[start_idx] in _NAME_EXCLUSIONS:
            start_idx += 1
        end_idx = len(words)
        while end_idx > start_idx and words[end_idx - 1] in _NAME_EXCLUSIONS:
            end_idx -= 1
        core_words = words[start_idx:end_idx]
        if len(core_words) < 2:
            continue
        # Recompute span for the trimmed core
        prefix = " ".join(words[:start_idx])
        if prefix:
            core_start = m.start() + len(prefix) + 1  # +1 for the space
        else:
            core_start = m.start()
        core_original = " ".join(core_words)
        core_end = core_start + len(core_original)
        span = (core_start, core_end)
        already_covered.add(span)
        matches.append(PIIMatch(
            type=PIIType.NAME,
            original=core_original,
            start=core_start,
            end=core_end,
            masked_partial=_mask_name_partial(core_original),
            masked_full="[NOME_MASCARADO]",
        ))

    # 5b. Single known Brazilian first names not already covered by a multi-word match
    for m in _RE_SINGLE_WORD.finditer(text):
        original = m.group()
        if original not in _BRAZILIAN_NAMES:
            continue
        if original in _NAME_EXCLUSIONS:
            continue
        overlaps_existing = any(
            m.start() >= s and m.end() <= e
            for (s, e) in already_covered
        )
        if overlaps_existing:
            continue
        matches.append(PIIMatch(
            type=PIIType.NAME,
            original=original,
            start=m.start(),
            end=m.end(),
            masked_partial=_mask_name_partial(original),
            masked_full="[NOME_MASCARADO]",
        ))

    return _remove_overlaps(matches)


def mask_text(
    text: str,
    level: MaskLevel = MaskLevel.FULL,
) -> tuple[str, list[PIIMatch]]:
    """Replace all PII in *text* with masked tokens.

    Replacements are applied right-to-left to preserve character offsets.

    Args:
        text: Input text to mask.
        level: FULL replaces with opaque tokens; PARTIAL uses obfuscated forms.

    Returns:
        A tuple of (masked_text, list_of_PIIMatch).
    """
    matches = detect_pii(text)
    result = text
    for match in sorted(matches, key=lambda m: m.start, reverse=True):
        replacement = match.masked_partial if level == MaskLevel.PARTIAL else match.masked_full
        result = result[: match.start] + replacement + result[match.end :]
    return result, matches


def has_pii(text: str) -> bool:
    """Return True if *text* contains any detectable PII.

    Args:
        text: Input text to check.

    Returns:
        True if at least one PII match is found.
    """
    return len(detect_pii(text)) > 0


def count_pii(text: str) -> dict[PIIType, int]:
    """Count PII occurrences per type.

    Args:
        text: Input text to scan.

    Returns:
        Dict mapping PIIType enum member to occurrence count.
    """
    counts: dict[PIIType, int] = {}
    for match in detect_pii(text):
        key = match.type
        counts[key] = counts.get(key, 0) + 1
    return counts
