# Backlog

## Content Hash / Replacement Detection

Current risk:
- URL-based de-duplication may miss FDA document replacements at the same URL.

Future improvement:
- Store URL, SHA256 content hash, Last-Modified, ETag, first_seen, last_seen.
- If URL is unchanged but content hash changes, re-parse and re-analyze the document.
- Preserve prior analysis and mark the document as replacement / errata / updated.

Suggested future state structure:

```json
{
  "seen_documents": {
    "pdf_url": {
      "first_seen": "",
      "last_seen": "",
      "content_hash": "",
      "last_modified": "",
      "etag": "",
      "analysis_run_id": "",
      "replacement_of": ""
    }
  }
}
```
