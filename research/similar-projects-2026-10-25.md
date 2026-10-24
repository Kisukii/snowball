# Existing projects closest to Snowball
Research date: 25 October 2026 (Asia/Calcutta).

## Decision
Reuse existing software. For the current Instagram-in-Chrome prototype, my recommendation is to keep Snowball's cat and simple guidance UI, and evaluate Nanobrowser's browser-control subsystem behind it. If replacing the entire desktop application is preferable, evaluate ClickyX first. For a Python-based teaching overlay, evaluate Bitshank-2338/clicky-windows.

These are engineering recommendations from repository documentation and selected source inspection, not runtime benchmarks. None of the downloaded candidates was installed, executed, or tested with Instagram in this investigation.

## Search scope and limits
Searched public web results for GitHub, Reddit, X/Twitter, Hacker News, DEV Community and HackerRank, plus project sites and official documentation. Used both broad category queries and exact project/repository searches. This is a broad public-source survey, not an exhaustive index of the internet.

Reddit post text and relevant discussion were readable. Hacker News founder posts and comments were readable. Two original Farza X status URLs returned HTTP 403; their posts were not independently read. The original repository links those tweets and directly states its open-source/private split. No close reusable project surfaced in the targeted HackerRank queries; results concerned its coding assessment assistant. Public visibility is not a code reuse license.

## Ranked reuse shortlist
Ranking reflects Snowball's needs: Windows, a visible companion, spoken step-by-step guidance, and optional browser actions.

| Candidate | What already exists | Reuse judgment | License evidence |
| --- | --- | --- | --- |
| [ClickyX](https://github.com/unn-Known1/clickyX) | Tauri/Rust/React desktop companion, overlays, voice, screenshot context, native input, local HTTP bridge. README documents Windows/Linux/macOS. | Closest full-app replacement candidate. Selected cua.rs confirms actual native input code, rather than only a future feature. Large stack change from Snowball. | MIT reported by repository license metadata and README. |
| [Clicky for Windows, Bitshank-2338](https://github.com/Bitshank-2338/clicky-windows) | Python/PyQt6 teaching companion, speech, animated pointing, repeat/next/stop, multiple model providers. | Closest Python guidance implementation. Copy selected mechanisms rather than assume the whole package is reliable. | MIT LICENSE directly read; PyQt6 has separate GPL/commercial terms. |
| [Nanobrowser](https://github.com/nanobrowser/nanobrowser) | Chrome/Edge extension controlling the user's existing browser, action permissions, page observation and execution. | Best browser-action candidate for current Snowball. No cat or older-adult teaching UI. | Apache-2.0 LICENSE directly read. |
| [Coopanion](https://github.com/Pal-AI-Lab/Coopanion) | Animated desktop pet, speech, computer use, user permissions, Windows/macOS/Linux builds. | Very close pet-plus-actions concept; evaluate separately before adopting the app wholesale. | Current LICENSE is AGPL-3.0-or-later with a Steamworks additional permission. README says releases through 0.1.10 were MIT; exact older tag and dependencies need verification before reuse. |
| [Skilly](https://github.com/tryskilly/skilly) | Screen-aware voice tutor, pointing, teaching skills, macOS app and embeddable web widget. | Strong guidance and lesson structure reference. Web widget is designed for embedding in a site; it does not itself grant access to Instagram. | Apache-2.0 for additions, with upstream Clicky MIT notices. |
| [Original Clicky](https://github.com/farzaa/clicky) | macOS screenshot/voice/pointing pipeline and floating companion. | Direct ancestor of the desired experience. Native Swift code needs porting for Windows. | MIT LICENSE directly read. README dated 27 April 2026 says existing code remains open, newer work is private. |
| [OpenClicky, prasanthsasikumar](https://github.com/prasanthsasikumar/openclicky) | macOS voice, visual pointer, dictation and Codex task handoff. | Useful pointing refinement and separation of guidance from task execution. | Repository describes MIT. |
| [Clicky for Windows, mesomya](https://github.com/mesomya/clicky-windows) | C#/.NET WPF port, screenshot context, local Whisper, spoken answers and flying pointer. | Alternative native Windows shell. README relies on an installed, signed-in Claude Code CLI; an existing paid plan is not zero total cost. | README describes MIT with original attribution. |
| [LocalClicky](https://github.com/tanavc1/LocalClicky) | Local-model variant of original Clicky, Swift package. | Useful local-provider reference; not a ready Windows replacement. | MIT shown by repository. |
| [Luma](https://github.com/nox-codes/Luma) | Native macOS screen-aware teacher and visual automation work. | Close teaching concept, but platform mismatch. | MIT reported by repository metadata. |
| [Windows-MCP](https://github.com/CursorTouch/Windows-MCP) | Windows UI state, accessibility-based interaction, mouse/keyboard and browser DOM mode. | Useful later for apps outside Chrome. It is an execution backend, with no cat or guided teaching UX. | MIT; current pyproject requires Python >=3.14, which must be checked against Snowball's runtime. |
| [PixelPaw AI](https://github.com/SRJ-ai/pixelpaw-ai) | Windows cat companion, procedural animation, click-through window, chat and agent status API. | Strong cat-shell reference. README says status API executes nothing; do not treat it as browser task automation. | Apache-2.0 reported by repository metadata. |

## Close products and repositories not selected for immediate copying
- [Ourguide](https://news.ycombinator.com/item?id=46769422): founder describes OS-wide screen overlays highlighting the next click, plus contextual Ask mode. Particularly close to guided use for older adults; an HN commenter describes a 99-year-old relative's need. The founder explicitly retains human clicking. A promise to release a pipeline is not evidence of a published licensed implementation.
- [Flubber](https://github.com/lordmacu/flubber-ai-companion): native animated pet plus screenshot/browser-agent features for Windows/macOS. Very close concept, but repository metadata returned license:null and the guessed root LICENSE path returned 404. Reuse permission remains unresolved; do not copy its implementation into Snowball on the basis of a public repository.
- [ParentHelper](https://github.com/Juribu/ParentHelper): unusually close audience fit: iOS assistant for a parent who cannot comfortably navigate English interfaces. Spoken Chinese, large controls, scripted task flows and a guided browser over selected sites. Repository metadata returned license:null; license permission remains unresolved. Useful product reference, not presently an approved code donor.
- [Super Agent Party](https://github.com/heshengtao/super-agent-party): animated AI companion platform with browser-control functionality explicitly described as accessibility assistance for elderly and other users. Current metadata reports AGPL-3.0; broader scope than the prototype needs.
- [Browser Use](https://github.com/browser-use/browser-use): alternative Python browser-automation foundation. Its project metadata advertises MIT; compare existing-browser integration before selecting it over Nanobrowser.
- [UI-TARS Desktop](https://github.com/bytedance/UI-TARS-desktop): alternative general GUI agent; not primarily a patient companion or teaching product.
- [Screenpipe](https://github.com/screenpipe/screenpipe/blob/main/LICENSE.md): useful screen-context product, but current source has a commercial license. Do not rely on older articles calling current main MIT.

## Selected source findings
### Bitshank Windows port
Inspected and staged universal_locator.py, base_provider.py, overlay.py and requirements.txt at revision c00831a545cdfc695559ce3a6ebe77547f19e352.

The locator draws a coarse 12-by-8 grid, asks a vision model to select a cell, crops around it and repeats with a 6-by-6 grid. It then maps the selected cell center into screen coordinates. Its own comment estimates 25–50 pixel accuracy at 1080p; this is an author estimate, not independently measured. If the second pass fails, the code falls back to the coarse-cell center. This is a useful pointing fallback but insufficient evidence for unattended clicks on small controls.

overlay.py supplies the real transparent Qt overlay, cursor flight and annotation logic. Reusing the timing/animation ideas in Snowball's current shell may cost less than migrating Tkinter to PyQt6. Riverbank documents PyQt's separate GPL/commercial licensing: https://www.riverbankcomputing.com/software/pyqt/intro

### Nanobrowser
Inspected and staged act.ts and perception/observe.ts at revision 19dc8e8a9be6ed06c0ef9ec7de8d84bf6a88c458.

Observation records accessible roles, names, frame/node references, partial capture information, and masked secrets. Pointer actions resolve/revalidate a target, wait for actionability, apply gates, dispatch an action and produce a receipt/page state. This is a stronger starting point for Instagram controls than estimating their centers from screenshots alone. A click receipt is still not proof the user's overall task succeeded.

The two TypeScript files import the surrounding controller, interaction, probe and protocol modules. They are study samples, not a standalone library. Integrate a pinned subsystem/fork with its dependencies rather than dropping these files into content.js. Decide how the extension's debugger/browser-control permissions fit the product.

### ClickyX
Selected source inspection of src-tauri/src/cua.rs confirms enigo mouse movement/click dispatch, rate limiting and platform handling. A success result there means input dispatch succeeded, not that the intended app operation completed. Its HTTP bridge could offer a way to attach Snowball's own visual character, but that adapter and Windows behavior need an actual local trial.

## Reuse plan for this repository
1. Preserve the existing cat and goal entry, speech and Stop/Repeat controls.
2. Evaluate a pinned Nanobrowser fork in a separate development profile; expose one next action at a time to Snowball.
3. Add a before-action hook: return the target rectangle, move the cat beside it and explain the step. Show me waits for the human; Help me do it dispatches the approved action.
4. Observe again after the step and compare the expected outcome. Re-plan if a dialog, navigation or layout change invalidates the target.
5. Use the Windows port's visual locator only when usable DOM/accessibility information is absent; ambiguous targets should ask for help.
6. Consider Windows-MCP only after browser tasks work, for native applications.
7. Evaluate ClickyX as the alternative whole-app base if maintaining Snowball's Python/Tkinter shell is no longer desirable.

Remaining original work: older-adult interaction design, task pacing, understandable confirmations, language support and tests on the actual websites. No inspected project establishes that it already delivers Snowball's complete experience reliably.

## Public discussion and discovery sources
- [Original author's source/private update](https://github.com/farzaa/clicky/blob/main/README.md)
- [Original author X update, access blocked here](https://x.com/FarzaTV/status/2043402737828962489)
- [Original author X demo, access blocked here](https://x.com/FarzaTV/status/2041314633978659092)
- [Reddit OpenClicky post and pointing-ambiguity discussion](https://www.reddit.com/r/SideProject/comments/1wbv0qa/i_built_an_opensource_version_of_heyclicky_a_mac/)
- [Reddit LocalClicky discovery](https://www.reddit.com/r/SideProject/comments/1uk1pha/local_clicky_all_credit_to_farza/)
- [HN Ourguide founder post and older-adult discussion](https://news.ycombinator.com/item?id=46769422)
- [Developer blog: Windows Clicky implementation](https://dev.to/bitshank2338/i-built-a-free-ai-that-reads-my-screen-and-answers-out-loud-no-api-key-runs-offline-with-ollama-15np)
- [Developer blog: OpenBlob early screen-aware companion](https://dev.to/southy404/im-building-a-local-ai-desktop-companion-that-sees-your-screen-and-you-can-help-shape-it-2ibh)
- [HackerRank AI features: assessment/coding context, not a close candidate](https://support.hackerrank.com/articles/9416207922-hackerrank%27s-ai-features)

The source samples under reuse-candidates are retained for comparison with license texts and a provenance manifest. They are not wired into the running application and are not complete installable checkouts.

