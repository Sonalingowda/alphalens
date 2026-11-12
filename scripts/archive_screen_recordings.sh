#!/usr/bin/env bash

set -Eeuo pipefail
umask 077

usage() {
  cat <<'EOF'
Usage: archive_screen_recordings.sh --volume-name NAME [options]

Copies exactly the two top-level .mov recordings from the source directory to
an external, mounted removable volume. Originals are never deleted.

Options:
  --volume-name NAME   Exact mounted volume name; required.
  --source-dir PATH    Source directory (default: ~/Library/ScreenRecordings).
  --dry-run            Validate source, volume and capacity without copying.
  --help               Show this help.

The destination is AlphaLens-Storage-Recovery-Archive. At least 20 GiB must
be free on the destination, in addition to the recordings and a 1 GiB margin.
EOF
}

source_dir="${HOME}/Library/ScreenRecordings"
volume_name=""
dry_run=0

while (($#)); do
  case "$1" in
    --volume-name)
      [[ $# -ge 2 ]] || { echo "--volume-name requires a value" >&2; exit 2; }
      volume_name="$2"
      shift 2
      ;;
    --source-dir)
      [[ $# -ge 2 ]] || { echo "--source-dir requires a value" >&2; exit 2; }
      source_dir="$2"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[[ -n "$volume_name" ]] || { echo "An exact --volume-name is required; refusing to guess a drive." >&2; exit 2; }
[[ -d "$source_dir" ]] || { echo "Source directory does not exist: $source_dir" >&2; exit 1; }

recordings=()
while IFS= read -r recording; do
  recordings[${#recordings[@]}]="$recording"
done < <(find "$source_dir" -maxdepth 1 -type f -name '*.mov' -print | sort)
if ((${#recordings[@]} != 2)); then
  echo "Expected exactly two top-level .mov recordings; found ${#recordings[@]}." >&2
  exit 1
fi

diskutil_bin="${DISKUTIL_BIN:-diskutil}"
volume_path="/Volumes/$volume_name"
volume_info="$($diskutil_bin info "$volume_path" 2>/dev/null)" || {
  echo "Mounted volume not found through diskutil: $volume_path" >&2
  exit 1
}

field() {
  local label="$1"
  awk -F': ' -v key="$label" '
    { lhs = $1; gsub(/^[[:space:]]+|[[:space:]]+$/, "", lhs) }
    lhs == key { print substr($0, index($0, ": ") + 2); exit }
  ' <<<"$volume_info"
}

[[ "$(field 'Volume Name')" == "$volume_name" ]] || { echo "Volume name mismatch; refusing to write." >&2; exit 1; }
[[ "$(field 'Mounted')" == "Yes" ]] || { echo "Volume is not mounted; refusing to write." >&2; exit 1; }
[[ "$(field 'Removable Media')" == "Removable" ]] || { echo "Volume is not confirmed removable; refusing to write." >&2; exit 1; }
[[ -d "$volume_path" && "$volume_path" != "/" ]] || { echo "Unsafe mount path; refusing to write." >&2; exit 1; }

available_kib="$(df -Pk "$volume_path" | awk 'NR == 2 {print $4}')"
[[ "$available_kib" =~ ^[0-9]+$ ]] || { echo "Could not determine destination free space." >&2; exit 1; }
minimum_kib=$((20 * 1024 * 1024))
required_kib=$((1024 * 1024))

total_bytes=0
for recording in "${recordings[@]}"; do
  size_bytes="$(stat -f '%z' "$recording")"
  total_bytes=$((total_bytes + size_bytes))
done
required_kib=$((required_kib + (total_bytes + 1023) / 1024))

if ((available_kib < minimum_kib || available_kib < required_kib)); then
  echo "Insufficient destination capacity: ${available_kib} KiB available; require at least 20 GiB and recordings plus 1 GiB margin." >&2
  exit 1
fi

archive_dir="$volume_path/AlphaLens-Storage-Recovery-Archive"
for recording in "${recordings[@]}"; do
  destination="$archive_dir/$(basename "$recording")"
  [[ ! -e "$destination" ]] || { echo "Destination exists; refusing to overwrite: $destination" >&2; exit 1; }
done

if ((dry_run)); then
  printf 'VALIDATION_OK volume=%s available_kib=%s recordings=%d total_bytes=%s destination=%s\n' \
    "$volume_name" "$available_kib" "${#recordings[@]}" "$total_bytes" "$archive_dir"
  exit 0
fi

mkdir -p "$archive_dir"
receipt="$archive_dir/archival-receipt-$(date -u +%Y%m%dT%H%M%SZ).txt"
[[ ! -e "$receipt" ]] || { echo "Receipt already exists; refusing to overwrite: $receipt" >&2; exit 1; }

{
  printf 'archive_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'volume_name=%s\nvolume_path=%s\nfilesystem=%s\n' "$volume_name" "$volume_path" "$(field 'File System Personality')"
  printf 'destination=%s\n' "$archive_dir"
  for recording in "${recordings[@]}"; do
    destination="$archive_dir/$(basename "$recording")"
    cp -p "$recording" "$destination"
    [[ -r "$destination" ]] || { echo "Copied file is not readable: $destination" >&2; exit 1; }
    original_size="$(stat -f '%z' "$recording")"
    copied_size="$(stat -f '%z' "$destination")"
    [[ "$original_size" == "$copied_size" ]] || { echo "Size mismatch: $destination" >&2; exit 1; }
    original_hash="$(shasum -a 256 "$recording" | awk '{print $1}')"
    copied_hash="$(shasum -a 256 "$destination" | awk '{print $1}')"
    [[ "$original_hash" == "$copied_hash" ]] || { echo "Checksum mismatch: $destination" >&2; exit 1; }
    cmp -s "$recording" "$destination" || { echo "Byte comparison failed: $destination" >&2; exit 1; }
    printf 'file=%s\ncopy=%s\nsize_bytes=%s\nsha256=%s\n' "$recording" "$destination" "$original_size" "$original_hash"
  done
} >"$receipt"

printf 'ARCHIVE_VERIFIED receipt=%s\n' "$receipt"
