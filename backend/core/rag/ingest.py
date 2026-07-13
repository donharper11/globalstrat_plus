"""
CC-11: Article processing pipeline for RAG ingestion.
Extracts text from PDFs/DOCX, chunks with section awareness,
assigns tags, embeds, and uploads to Qdrant.
"""
import re
import uuid


def extract_text_from_pdf(filepath):
    """
    Extract text from a PDF file.
    Returns: list of (page_number, text) tuples.
    """
    import pypdf

    reader = pypdf.PdfReader(filepath)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            pages.append((i + 1, text.strip()))
    return pages


def extract_text_from_docx(filepath):
    """Extract text from a DOCX file."""
    import docx
    doc = docx.Document(filepath)
    text = '\n'.join([para.text for para in doc.paragraphs if para.text.strip()])
    return [(1, text)]  # Treat as single "page"


# ---------------------------------------------------------------------------
# Section-aware chunking
# ---------------------------------------------------------------------------

SECTION_PATTERNS = [
    r'\n(?:Abstract|ABSTRACT)\s*\n',
    r'\n(?:\d+\.?\s+)?(?:Introduction|INTRODUCTION)\s*\n',
    r'\n(?:\d+\.?\s+)?(?:Literature Review|LITERATURE REVIEW|Background|BACKGROUND)\s*\n',
    r'\n(?:\d+\.?\s+)?(?:Methodology|METHODOLOGY|Method|METHODS|Research Design)\s*\n',
    r'\n(?:\d+\.?\s+)?(?:Results|RESULTS|Findings|FINDINGS|Analysis|ANALYSIS)\s*\n',
    r'\n(?:\d+\.?\s+)?(?:Discussion|DISCUSSION)\s*\n',
    r'\n(?:\d+\.?\s+)?(?:Conclusion|CONCLUSIONS?|Summary|SUMMARY)\s*\n',
    r'\n(?:\d+\.?\s+)?(?:References|REFERENCES|Bibliography|BIBLIOGRAPHY)\s*\n',
]


def chunk_article(pages, max_chunk_size=1500, overlap=200):
    """
    Chunk article text with section awareness.
    Returns: list of {text, label, char_start, char_end}
    """
    full_text = '\n\n'.join([text for _, text in pages])

    # Find section boundaries
    boundaries = [(0, 'beginning')]
    for pattern in SECTION_PATTERNS:
        for match in re.finditer(pattern, full_text):
            label = match.group().strip().lstrip('0123456789. ')
            boundaries.append((match.start(), label))

    boundaries.sort(key=lambda x: x[0])
    boundaries.append((len(full_text), 'end'))

    # Extract sections
    sections = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i][0]
        end = boundaries[i + 1][0]
        label = boundaries[i][1]
        text = full_text[start:end].strip()

        if not text or label.lower() in ('references', 'bibliography', 'end'):
            continue

        sections.append({
            'text': text,
            'label': label,
            'char_start': start,
            'char_end': end,
        })

    # Chunk sections exceeding max_chunk_size
    chunks = []
    for section in sections:
        if len(section['text']) <= max_chunk_size:
            chunks.append(section)
        else:
            paragraphs = section['text'].split('\n\n')
            current_chunk = ''
            current_start = section['char_start']

            for para in paragraphs:
                if len(current_chunk) + len(para) + 2 > max_chunk_size and current_chunk:
                    chunks.append({
                        'text': current_chunk.strip(),
                        'label': section['label'],
                        'char_start': current_start,
                        'char_end': current_start + len(current_chunk),
                    })
                    # Overlap
                    overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else ''
                    current_chunk = overlap_text + '\n\n' + para
                    current_start += len(current_chunk) - len(overlap_text) - len(para) - 2
                else:
                    current_chunk += '\n\n' + para if current_chunk else para

            if current_chunk.strip():
                chunks.append({
                    'text': current_chunk.strip(),
                    'label': section['label'],
                    'char_start': current_start,
                    'char_end': section['char_end'],
                })

    return chunks


# ---------------------------------------------------------------------------
# Tag assignment
# ---------------------------------------------------------------------------

TAG_RULES = {
    'market_entry': [
        'market entry', 'entry mode', 'entry strategy', 'foreign market',
        'internationalization', 'internationalis',
    ],
    'country_selection': [
        'country selection', 'market selection', 'market attractiveness',
        'country risk', 'analytic hierarchy', 'ahp', 'multicriteria',
    ],
    'trade_policy': [
        'tariff', 'protectionism', 'trade agreement', 'trade bloc',
        'mercantilism', 'import', 'export quota',
    ],
    'political_risk': [
        'political risk', 'j-curve', 'j curve', 'bremmer',
        'corruption', 'authoritarian', 'instability',
    ],
    'globalization': [
        'globalization', 'globalisation', 'multinational', 'mne',
        'global strategy', 'international business',
    ],
    'competition': [
        'competitive advantage', 'five forces', 'porter',
        'competitive strategy', 'rivalry', 'market share',
    ],
    'strategy': [
        'strategy', 'strategic', 'ansoff', 'bcg matrix', 'rbv',
        'resource based', 'diversification', 'competitive superiority',
    ],
    'marketing': [
        'marketing', 'consumer', 'brand', 'pricing', 'promotion',
        'distribution', 'stp', 'segmentation', '4p',
    ],
    'sustainability': [
        'sustainability', 'csr', 'corporate social', 'esg',
        'governance', 'environmental', 'ethical', 'green',
    ],
    'finance': [
        'finance', 'accounting', 'dupont', 'ratio', 'investment',
        'valuation', 'currency', 'hedging',
    ],
    'supply_chain': [
        'supply chain', 'logistics', 'sourcing', 'procurement',
        'transport', 'distribution channel',
    ],
    # CC-11 SC taxonomy extensions (rework): finer supply-chain topics so the
    # SC corpus can be topic-filtered, not just bucketed under 'supply_chain'.
    'global_sourcing': [
        'global sourcing', 'integrated sourcing', 'supplier selection',
        'strategic sourcing', 'outsourcing', 'make or buy', 'supply base',
    ],
    'logistics': [
        'logistics', 'freight', 'shipping', 'incoterms', 'modal', 'warehousing',
        'container', 'lead time', 'distribution network',
    ],
    'trade_finance': [
        'trade finance', 'letter of credit', 'currency hedging', 'fx hedge',
        'export credit', 'sinosure', 'forward contract', 'import or export',
        'payment terms',
    ],
    'compliance': [
        'compliance', 'uflpa', 'cbam', 'forced labor', 'export control',
        'customs', 'sanctions', 'entity list', 'due diligence', 'trade bloc',
        'trade agreement',
    ],
    'resilience': [
        'resilience', 'disruption', 'supply chain risk', 'business continuity',
        'global risks', 'shock', 'vulnerability', 'contingency',
    ],
    'chinese_institutional': [
        'china', 'chinese', 'belt and road', 'guanxi', 'state-owned',
        'made in china', 'dragon',
    ],
    'technology': [
        'technology', 'digital', 'artificial intelligence',
        'blockchain', 'information system', 'big data', 'cyber',
    ],
    'culture': [
        'culture', 'hofstede', 'cultural distance', 'psychic distance',
        'bourdieu', 'sociology',
    ],
    'innovation': [
        'innovation', 'r&d', 'research and development',
        'disruptive', 'technology transfer',
    ],
    'emerging_market': [
        'emerging market', 'developing', 'bric', 'africa',
        'asean', 'china', 'india', 'brazil', 'global south',
    ],
    'leadership': [
        'leadership', 'management', 'ceo', 'executive',
        'organizational culture', 'drucker',
    ],
    'regulation': [
        'regulation', 'compliance', 'governance', 'law', 'legal',
        'regulatory',
    ],
}


def assign_tags(filename, text_sample):
    """
    Assign rag_source_tags based on filename patterns and content.
    Returns list of tag strings.
    """
    tags = set()
    search_text = (filename + ' ' + text_sample).lower()

    for tag, keywords in TAG_RULES.items():
        if any(kw in search_text for kw in keywords):
            tags.add(tag)

    # Always add the folder as a tag
    if 'international_business' in filename.lower() or '/international_business/' in filename:
        tags.add('international_business')
    if '/strategy/' in filename or filename.startswith('strategy/'):
        tags.add('strategy')

    if not tags:
        tags.add('general')

    return list(tags)


# ---------------------------------------------------------------------------
# Qdrant upload
# ---------------------------------------------------------------------------

def ingest_article(filepath, catalog_entry, client, collection_name):
    """
    Process one article: extract text, chunk, embed, upload to Qdrant.
    Returns: (chunks_uploaded, tags, error_message_or_None)
    """
    from core.rag.embeddings import get_embedding
    from qdrant_client.models import PointStruct

    ext = catalog_entry.get('file_type', '').lower()
    try:
        if ext == '.pdf':
            pages = extract_text_from_pdf(filepath)
        elif ext == '.docx':
            pages = extract_text_from_docx(filepath)
        else:
            return 0, [], f"Unsupported format: {ext}"
    except Exception as e:
        return 0, [], f"Extraction error: {e}"

    if not pages:
        return 0, [], "No text extracted"

    # Tag assignment: keyword auto-tags (filename + content) merged with any
    # curated tags in the catalog. A curated `topic` (single primary subject)
    # takes precedence; otherwise fall back to the first auto tag.
    full_text_sample = ' '.join([t for _, t in pages])[:2000]
    auto_tags = assign_tags(
        catalog_entry.get('relative_path', catalog_entry.get('filename', '')),
        full_text_sample,
    )
    tags = sorted(set(auto_tags) | set(catalog_entry.get('tags') or []))
    topic = catalog_entry.get('topic') or (tags[0] if tags else 'general')

    # Chunk
    chunks = chunk_article(pages)
    if not chunks:
        return 0, tags, "No chunks generated"

    # Embed and upload
    title = catalog_entry.get('title') or catalog_entry.get('filename', '')
    points = []
    embed_errors = 0

    for i, chunk in enumerate(chunks):
        embed_text = f"Title: {title}\nSection: {chunk['label']}\n\n{chunk['text']}"

        try:
            embedding = get_embedding(embed_text)
        except Exception:
            embed_errors += 1
            continue

        point_id = str(uuid.uuid4())
        points.append(PointStruct(
            id=point_id,
            vector=embedding,
            payload={
                'text': chunk['text'],
                'title': title,
                'source': catalog_entry.get('filename', ''),
                'folder': catalog_entry.get('relative_path', ''),
                'section': chunk['label'],
                'chunk_index': i,
                'total_chunks': len(chunks),
                'topic': topic,
                'tags': tags,
                'page_count': catalog_entry.get('page_count'),
                'author': catalog_entry.get('author'),
            },
        ))

    # Upload in batches
    batch_size = 50
    uploaded = 0
    for j in range(0, len(points), batch_size):
        batch = points[j:j + batch_size]
        client.upsert(
            collection_name=collection_name,
            points=batch,
        )
        uploaded += len(batch)

    error_msg = None
    if embed_errors > 0:
        error_msg = f"{embed_errors} chunks failed embedding"

    return uploaded, tags, error_msg
