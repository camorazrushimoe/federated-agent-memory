# Delta — Raw Archive

## REMOVED Requirements

### Requirement: Immutable append-only storage
**Removed.** Raw-session storage is delegated to Google Memory Bank; the system
no longer maintains its own append-only JSON archive.

### Requirement: Tenant-namespaced path layout
**Removed.** Local filesystem path layout no longer applies — storage is managed
by Google Memory Bank.

### Requirement: Atomic writes
**Removed.** Write durability and atomicity are the responsibility of Google
Memory Bank.

### Requirement: Session record schema
**Removed.** Session record shape is defined by Google Memory Bank, not a
self-managed schema.

### Requirement: Idempotent close
**Removed.** Session lifecycle is handled by the Gemini Enterprise session
mechanism.
