# 0006. Encrypt resumes before storage; serve them through short-lived signed links

**Status:** Accepted

## Context
Resumes are personal data. They are stored on local disk in development and in an
S3-compatible bucket in production, and opened by the owner, recruiters of jobs the
seeker applied to, and admins.

## Decision
- Files are encrypted with Fernet (AES-128-CBC + HMAC-SHA256) in the application before
  they reach any storage backend, with a dedicated `FILE_ENCRYPTION_KEY`.
- Storage keys are random (`resumes/<user>/<uuid>.pdf`), never derived from file names.
- Downloads go through `POST /api/resumes/{id}/link`, which returns a URL signed with
  HMAC-SHA256 over (resume, viewer, expiry), valid for 5 minutes. Access is re-checked
  when the link is used, and every access by someone other than the owner is audited.
- Uploads are scanned (heuristics, optional ClamAV) and parsed in a sandboxed subprocess.

## Consequences
- A leaked bucket or disk snapshot does not expose resumes; losing the key loses the files,
  so it must be backed up with the database.
- Presigned S3 URLs cannot be used (the bucket holds ciphertext), so downloads stream
  through the API.
- A signed link can be shared for its 5-minute lifetime; it names the viewer it was issued
  to, and that viewer's access is re-checked.

## Alternatives considered
- **Bucket-side encryption only** (SSE): protects against disk theft at the provider, not
  against bucket misconfiguration or leaked credentials.
- **Bearer-token downloads**: cannot be opened in a new tab without fetching into a blob.
