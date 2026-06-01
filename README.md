# Buyol Asset Pipeline

Asset-heavy research repo for Buyol visual generation, custom SF Symbol experiments, Blender files, references, and export pipeline notes.

## Status

This repository is intentionally not part of the main GitHub profile showcase. It is public for traceability, but it contains many generated and binary asset files and should be treated as a research/archive workspace rather than a lightweight developer tool.

Current repository pack size is roughly `813 MiB`. The largest tracked files are generated `.glb` and `.fbx` exports under `asset-pipeline/exports/`.

This repo should not be pinned on the public profile. The portfolio-facing work should stay focused on local-first developer tools, AI agent workflows, security automation, and reproducible tooling.

## Usage And Rights

This repository is published as a read-only research reference, not as a reusable asset pack.

- No open-source license is granted for generated visual assets, Blender files, reference images, or exported model files unless a file states otherwise.
- Do not reuse, redistribute, or train on the generated assets without explicit permission.
- Source notes, prompts, and workflow documentation are for inspection only while this repo remains an archive.
- See [RIGHTS.md](RIGHTS.md) for the explicit reuse boundary.

## Recommended Cleanup

- Keep source prompts, scripts, manifests, and small reference docs in git.
- Move generated `.glb`, `.fbx`, large `.blend`, and image outputs to Git LFS or GitHub release assets before using this repo as a public reference.
- Add a compact manifest that maps each asset name to its prompt, source file, exported files, and intended app usage.
- Keep future showcase work in a separate small repo if the output should be easy to clone.

## Decision Path

The preferred end state is one of:

1. Make the repository private if it remains mostly personal/generated asset work.
2. Archive the repository on GitHub if it should stay public only for traceability.
3. Split a small public showcase repo from this archive and move large generated assets to releases, Git LFS, or private storage.
