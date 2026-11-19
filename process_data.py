"""
process_data.py

Convert data/raw/*.jsonl into:
data/processed/chunks.jsonl

Each chunk contains:
- Listing metadata
- A context header
- A portion of the property description
- A stable chunk ID
"""

import json
import os
import re
import uuid


# ---------------------------------------------------------
# Text chunking
# ---------------------------------------------------------

def split_sentences(text):

    text = str(text or "")

    return [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?])\s+|\n+",
            text,
        )
        if sentence.strip()
    ]


def chunk_text(text, max_words=200):
    """Split text into chunks of at most max_words."""

    chunks = []
    current = []
    count = 0

    for sentence in split_sentences(text):

        words = sentence.split()

        # Handle one very long sentence.
        if len(words) > max_words:

            if current:
                chunks.append(" ".join(current))
                current = []
                count = 0

            for i in range(0, len(words), max_words):
                chunks.append(
                    " ".join(words[i:i + max_words])
                )

            continue

        # Close current chunk if the next sentence overflows.
        if count + len(words) > max_words:

            if current:
                chunks.append(" ".join(current))

            current = []
            count = 0

        current.append(sentence)
        count += len(words)

    if current:
        chunks.append(" ".join(current))

    return chunks


# ---------------------------------------------------------
# Metadata
# ---------------------------------------------------------

def context_header(record):

    parts = [
        record.get("title", ""),
        record.get("property_type", ""),
        record.get("listing_type", ""),
        record.get("location", ""),
        record.get("country", ""),
    ]

    price = record.get("price")

    if price not in (None, ""):

        currency = record.get("currency", "")

        parts.append(
            f"Price: {price} {currency}".strip()
        )

    bedrooms = record.get("bedrooms")

    if bedrooms not in (None, ""):
        parts.append(f"{bedrooms} bedrooms")

    area = record.get("area_sqm")

    if area not in (None, ""):
        parts.append(f"{area} sqm")

    return " | ".join(
        str(part)
        for part in parts
        if part not in (None, "")
    )


def make_chunk(record, piece, index):

    url = record.get("url", "")

    chunk_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{url}#{index}",
        )
    )

    header = context_header(record)

    full_text = (
        f"{header}\n{piece}"
        if header
        else piece
    )

    return {
        "chunk_id": chunk_id,

        "source": record.get("source", "unknown"),
        "listing_type": record.get("listing_type", ""),

        "title": record.get("title", ""),
        "url": url,

        "location": record.get("location", ""),
        "country": record.get("country", ""),

        "property_type": record.get("property_type", ""),
        "price": record.get("price", ""),
        "currency": record.get("currency", ""),

        "bedrooms": record.get("bedrooms", ""),
        "area_sqm": record.get("area_sqm", ""),

        "chunk_text": full_text,
    }


# ---------------------------------------------------------
# Main processing
# ---------------------------------------------------------

def main():

    raw_dir = "data/raw"
    processed_dir = "data/processed"

    if not os.path.isdir(raw_dir):
        raise FileNotFoundError(
            f"Raw data folder not found: {raw_dir}"
        )

    os.makedirs(
        processed_dir,
        exist_ok=True,
    )

    chunks_file = os.path.join(
        processed_dir,
        "chunks.jsonl",
    )

    total_records = 0
    total_chunks = 0
    skipped_records = 0

    raw_files = sorted(
        filename
        for filename in os.listdir(raw_dir)
        if filename.endswith(".jsonl")
    )

    if not raw_files:
        raise FileNotFoundError(
            f"No JSONL files found in {raw_dir}"
        )

    with open(
        chunks_file,
        "w",
        encoding="utf-8",
    ) as fout:

        for filename in raw_files:

            file_path = os.path.join(
                raw_dir,
                filename,
            )

            print(f"Processing {filename}...")

            with open(
                file_path,
                "r",
                encoding="utf-8",
            ) as fin:

                for line_number, line in enumerate(fin, start=1):

                    if not line.strip():
                        continue

                    try:
                        record = json.loads(line)

                    except json.JSONDecodeError as error:

                        print(
                            f"Skipping invalid JSON: "
                            f"{filename}, line {line_number}: {error}"
                        )

                        skipped_records += 1
                        continue

                    if not isinstance(record, dict):
                        skipped_records += 1
                        continue

                    total_records += 1

                    description = record.get("description", "")
                    detail_text = record.get("detail_text", "")

                    body = "\n".join(
                        str(text)
                        for text in (
                            description,
                            detail_text,
                        )
                        if text
                    )

                    if not body.strip():

                        # Keep a listing even if it has no description.
                        body = context_header(record)

                    if not body.strip():
                        skipped_records += 1
                        continue

                    pieces = chunk_text(body)

                    if not pieces:
                        pieces = [body]

                    for index, piece in enumerate(pieces):

                        chunk = make_chunk(
                            record,
                            piece,
                            index,
                        )

                        fout.write(
                            json.dumps(
                                chunk,
                                ensure_ascii=False,
                            ) + "\n"
                        )

                        total_chunks += 1

    print("\nProcessing complete.")
    print(f"Records processed: {total_records}")
    print(f"Chunks written: {total_chunks}")
    print(f"Records skipped: {skipped_records}")
    print(f"Output file: {chunks_file}")


if __name__ == "__main__":
    main()