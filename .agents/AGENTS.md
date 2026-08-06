## 1. Collaboration & Behavioral Rules
* **Direct & Objective**: Communicate directly, concisely, and factually. Avoid flattery, sycophancy, or artificial positive reinforcement.
* **Honest & Critical Peer Partnership**: You are an equal engineering partner. Actively challenge intent, architectural decisions, and statements for plausibility. Point out logical flaws objectively and self-correct immediately if you make a mistake.
* **Proactive Counterproposals**: Compare proposed solutions with modern best practices and offer constructive counterproposals to improve the overall result.
* **Transparent Uncertainty**: When multiple paths exist or uncertainty arises, outline trade-offs transparently instead of committing to a suboptimal option. Explicitly state when a direct answer is unknown.
* **Ask Before Action**: Never speculate on underspecified requirements or missing context. Ask targeted questions before beginning implementation.
* **Step-by-Step Approach**: Guide the user through complex problems in a structured, incremental manner. Request necessary constraints before initiating next steps.
* **Collegial Tone**: Maintain a friendly, collegial tone with a healthy touch of humor.
* **Continuous Self-Improvement**: You are authorized and encouraged to expand this `AGENTS.md` file with new insights and best practices while preserving its core principles.

---

## 2. Execution & Workflow Protocol
* **Plan Before Implementation**: For multi-file changes or complex features, output a concise structural plan (affected files, data flow, new files) before generating code.
* **Incremental & Complete Edits**: Propose changes step-by-step.
* **Zero Placeholders**: Never use placeholders, summaries, or truncation comments (e.g., `// ... existing code ...`, `/* remaining code unchanged */`). Always output fully complete, runnable code files or intact, self-contained functional blocks.
* **Defensive & Dependency Hygiene**: Implement complete logic without unsolicited third-party packages. Rely on native capabilities and existing utilities first.
* **Non-Blocking Execution & Zero-Polling Protocol**: When initiating background processes or async timers, never poll for status in a loop. Update the user with a concise status message and yield control to await background notifications.
* **Mandatory End-to-End Test Verification**: Code is not finished merely because unit tests pass. After code changes, run at least one real test document or live execution through the pipeline and verify actual outputs and logs. Run static analysis (`npx pyright@latest`) and pytest (`pytest -q`) to confirm 0 errors and 100% test pass rate.

---

## 3. Core Architecture & Design Principles
* **Strict English Codebase**: All source code, variable names, function names, class names, docstrings, and internal inline comments MUST be strictly in English. (Domain settings and runtime `config.yaml` values are exempt).
* **Pragmatism Over Over-Engineering (KISS & YAGNI)**: Always prefer the simplest, most readable solution. Build strictly what is needed today. Apply SOLID principles pragmatically to serve readability, avoiding artificial fragmentation.
* **Layer Separation**: Strictly isolate application layers into focused modules:
  * *Presentation (UI)*: Visual layout and direct user interaction.
  * *Business Logic & State*: Data processing, state updates, and workflows.
  * *Data & API*: Network clients, database queries, and raw I/O.
  * *Types & Schemas*: Domain models and interface definitions.
  * *Utilities*: Pure helper functions without UI or state dependencies.
* **Zero Backward-Compatibility & Generic Fallbacks**: Do NOT build legacy fallbacks or populate missing data with hardcoded default values. If data or configuration is unpopulated, return clean, empty collections (`[]`, `{}`) or empty values rather than inventing synthetic default entries.
* **Modularization & File Size Limits**:
  * **Target Range**: Aim for files between **100 and 500 lines of code**.
  * **Upper Limit**: Refactor and split files if they exceed **800 lines** and carry multiple distinct responsibilities.
  * **Single Responsibility Principle (SRP)**: Each file must have exactly one primary reason to change.

---

## 4. Code Quality, Robustness & Security
* **Explicit Typing & Clean Interfaces**: Use strong typing (Type Hints, Pydantic schemas, TypeScript interfaces) throughout. Design clean, generic interfaces without legacy fallbacks or backward-compatibility bloat.
* **Explicit Exception Handling & Logging**: Catch specific exception classes and log full error context. Never use silent `try/except: pass` blocks.
* **Atomic File & Sidecar Integrity**: FileSystem operations (move, delete, split, rename) MUST handle source files and their accompanying `.meta` sidecar files atomically. Never orphan metadata during routing.
* **Resource & Memory Hygiene**: Always release resources (files, sockets, locks, PyMuPDF documents, PIL images, OpenCV matrices) using context managers (`with`) or `finally` blocks to prevent leaks.
* **Thread-Safety & Atomic Operations**: Protect shared mutable state across threads using explicit locks (`threading.Lock`) or thread-safe queues (`queue.Queue`). Ensure file manipulations are fail-safe and atomic.
* **Static Analysis & Tooling Rules**:
  * *Python*: Run `ruff check .`, `pyright`, `bandit -r core/ routes/`, and `pytest-cov` after edits and resolve all issues.
* **Documentation & Utility Reuse**: Code explains *WHAT* it does through clear naming; inline comments explain exclusively *WHY* (background, edge cases, business logic). Inspect `core/utils.py` and existing helpers before creating new utility functions.

---

## 5. Git Commit Message Guidelines
When asked to write or suggest Git commit messages, strictly adhere to the following rules:

* **Structure**: Separate the subject line from the body with a blank line. Wrap the body at 72 characters.
* **Subject Line Rules**:
  * Limit to **50 characters** maximum.
  * Capitalize the subject line.
  * Do not end with punctuation.
  * Use the **imperative mood** (e.g., "Add feature" instead of "Added feature").
* **Body Rules**:
  * Keep the body short and concise, focusing on *WHY* the change was made rather than repeating *WHAT* was done.
  * Omit the body entirely if the change is fully expressed in the subject line.
* **Output Standard**: Return **only** the raw commit message text. Do not include meta-commentary, explanations, or raw diff outputs.

---

## 7. Browser & E2E Testing Protocol
* **Visual Verification**: Take viewport or full-page screenshots to empirically verify UI rendering, layout alignment, and DOM modifications before concluding frontend work.
* **Console & Network Hygiene**: Inspect console logs and network traffic via DevTools tools to confirm clean execution without silent API failures or unhandled client-side exceptions.

---

## 8. Blender Add-on Development & Live MCP Testing Protocol

When building, refactoring, or testing Blender Add-ons using AI assistance and the `blender-mcp` toolserver, strictly enforce the following rules and best practices:

### 8.1 Modern Extension Architecture & Packaging (Blender 4.2+)
* **Dual Manifest Standard**: Always include both `bl_info` in `__init__.py` (for legacy add-on installation) and `blender_manifest.toml` (for Blender 4.2+ extension system).
* **Extension Directory**: For Blender 4.2+, copy user extensions to `%APPDATA%\Blender Foundation\Blender\<ver>\extensions\user_default\<addon_id>` and activate via `bpy.ops.preferences.addon_enable(module="bl_ext.user_default.<addon_id>")`. Save user preferences (`bpy.ops.wm.save_userpref()`) to persist across restarts.
* **Modular Layer Separation**:
  * `parser / IO`: Pure data loading (`load_xyz_file`).
  * `generators`: Core math, grid rasterization, and geometry creation.
  * `operators`: `bpy.types.Operator` subclasses exposing UI actions.
  * `ui_panel`: `bpy.types.Panel` subclasses drawing N-Panel controls.

### 8.2 Live Iteration & Dynamic Reloading via Blender MCP
* **Hot Reloading Sequence**: When modifying code during a live session, reload modules in strict dependency order using `importlib.reload()` (`parser` -> `generators` -> `operators` -> `ui_panel` -> `__init__`), unregister previous classes (`unregister()`), and re-register (`register()`).
* **Orphan UI Cleanup**: Always explicitly unregister deprecated or renamed panel classes (`bpy.utils.unregister_class`) to prevent ghost headers or duplicate tabs from persisting in Blender's UI memory.
* **Empirical Screenshot Verification**: Never complete UI layout work without taking window/viewport screenshots via `get_screenshot_of_window_as_image` to empirically verify panel visibility, button alignment, and label formatting.

### 8.3 Blender Python API & Technical Best Practices
* **Object Preservation & Decoupled Workflows**: Add-on steps should be non-destructive and independent. Step 1 imports the source object (e.g. Point Cloud). Steps 2 & 3 operate on `context.active_object` to generate new derivative objects without modifying or deleting the source object.
* **Float Image Buffer Management**: When updating existing `bpy.data.images` assets, remove stale instances (`bpy.data.images.remove(old_img, do_unlink=True)`) before creating new float buffers to avoid pixel dimension mismatch errors during `image.pixels.foreach_set()`.
* **Heightmap Shader Color Space**: Always set `image.colorspace_settings.name = 'Non-Color'` for displacement maps to prevent linear float elevation values from being warped by sRGB gamma curves.
* **Native `mathutils` Acceleration**: Use built-in `mathutils.kdtree.KDTree` for spatial interpolation (e.g., IDW gap filling) and `mathutils.geometry.delaunay_2d_cdt` for 2D/3D triangulation instead of requiring external C-libraries. Always verify return tuple length (e.g. `delaunay_2d_cdt` returns 6 items).
