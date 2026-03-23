import asyncio
import datetime
import json

import logging
from pathlib import Path
import traceback

from openai import BaseModel
from app.llm_services.any_model import AnyModel
from app.models.chat_message import ChatMessage, ModelWithParameters
from app.models.file_category import FileCategory
from app.services.imagery_all.stateful_imagery import StatefulImageryModule
from app.services.imagery_all.stateful_imagery_4_no_shadow_perspective import (
    StatefulImageryModule4NoShadowPerspective,
)
from app.services.imagery_all.stateful_imagery_6_human_friend_rotation import (
    StatefulImageryHumanFriendRotationModule_6,
)
from app.services.imagery_all.stateful_imagery_7_lighter_shadow import (
    StatefulImageryHumanFriendRotationModule_7,
)
from app.services.imagery_all.stateful_imagery_8_with_initial_rotation import (
    StatefulImageryWithInitialRotationModule_8,
)
from app.services.s3_services import S3UploadServices
from app.utils.file_utils import CustomJSONEncoder
from app.utils.json_utils import parser_json

logger = logging.getLogger(__name__)


# "A": "unknown"|"matched"|"probably_not_match"


reasoner_with_answer_ORG = """

### Task

This task involves **visual 3D modeling and analysis**.
The question of the type
```
Question: The left image shows the original cube stack made of equal-sized small cubes. Which of the options on the right cannot be obtained by rotating the original cube stack? Please answer from options A, B or C.
```
So, it ask to find the odd one, and you should answer this question at the end, but the most import thing is the WAY you should address the problem.
You have to, by using the imagery module, find the rotation itself to get to the `original`. So, you are not just answering the question, but FIND THE SEQUENCE OF ROTATION OPERATION that brings to the `original` in the angle it is given in the problem image.
For the alternative that you find the rotation, it is not the answer. Only the one you can not find after an exhaustive search, and only one, this will be the answer. For all others it is imperative that you find the rotation sequence. 

---

### About the imagery module

The **imagery module** offers the capability to rotate objects and get the snapshot for the camera angle position.

The **interaction** proceeds in **turns**.
Each turn follows this pattern:

1. **Your turn**: Analyze the provided images and reasoning notes (stored “memory” from prior turns).
   Then, produce your output, consisting of (a) updated reasoning and (b) rotation commands for the imagery module.
2. **Imagery module’s turn**: The module executes your commands, generates new images, and supplies them as context for the next iteration.

The question asks you to rotate the original to match the alternative, but it is the same to rotate the alternative to match the original. In this task, the imagery module will provide rotation capability of the alternatives, so that you have to match the original.

The **imagery module is stateful** — it preserves each object’s camera position between iterations.

> ⚠️ **Important:**
>
> * Each call to you represents **one iteration (one turn)** in the ongoing process.
> * **Do not simulate multiple turns** or the imagery module’s responses.
> * In each turn, **produce output**, then stop after returning a JSON object.

---

### Command System

**Valid targets:**
`A`, `B`, `C`

**Operations:**
`left`, `right`, `up`, `down`, `rotate:cw`, `rotate:ccw`

**Operation details:**

* `left`: rotate object left by the specified degree.
* `right`: rotate object right by the specified degree.
* `up`: tilt object upward by the specified degree.
* `down`: tilt object downward by the specified degree.
* `rotate:cw`: rotate object clockwise by the specified degree.
* `rotate:ccw`: rotate object counterclockwise by the specified degree.

Note: Rotation directions in the command are defined relative to the object, not the camera. As a result, they are the inverse of camera rotations. For example, `right:15` rotates the object 15° to the right. This is equivalent to **moving** the camera 15° to the left, or `yaw:-15`.

**Command syntax:**
Each command consists of the operation and degree separated by a colon.
Examples:

* `"left:15"`
* `"rotate:cw:30"`

**Rotation sequence syntax:**
A rotation sequence is a comma-separated list of commands applied in order.
Examples:

* `"left:15,right:15,up:15"`
* `"right:10,right:10,right:10"`

---

### Output Format

For each iteration (turn), return output in the following JSON format:

```json
{
  "memory": {
    "current_iteration": integer (e.g., 1, 2, 3...),
    "current_alternative_focusing": "A",
    "rationale": "Analysis of the most recent image result",
    "partial_conclusion": {
        "A": "unknown|match_rotation_not_found_yet|match_rotation_found",
        "B": ...
        "C": ...
    },
    "next_alternative_to_focus": "A",
    "estimate_rotation_distance_to_original": "Put the best estimated distance to the target, in direction and degrees, to direct your next action",
  },
  "commands": [
    {
      "target": "A|B|C",
      "rotation_sequence": "right:15,right:15,up:10"
    }
  ],
  "final_answer": "A|B|C|null"
}
```

**Field explanations:**

* **`memory.current_iteration`**:
  Integer indicating which iteration/turn this output corresponds to (starting from `1` and increasing each turn).

* **`commands`**:

  * List of rotation directives for one or more targets.
  * Each `target` corresponds to a model that will generate a **composite image**: the sequence of rotations you specify will produce one snapshot per rotation step.
  * For example:

    * `"right:10,right:10,right:10"` generates 3 incremental views.
    * A `"right:0"` command produces an image from the current view (no rotation).

* **`final_answer`**:

  * Set the solution label (`"A"`, `"B"`, or `"C"`) if you have reached ~~to~~ a conclusion, or `null` otherwise.

**IMPORTANT** Always output as json object. Even for final answer.




""".strip()

reasoner_with_answer_GEMINI = """
This task involves **visual 3D modeling and analysis** using an auxiliary tool called the **“imagery module.”**
Your goal is to solve the problem through an *imagery-based reasoning process* (described below), interacting iteratively with this module.

The **imagery module** offers the capability to rotate objects and get the snapshot for the camera angle position.

The **interaction** proceeds in **turns**.
Each turn follows this pattern:

1. **Your turn**: Analyze the provided images and reasoning notes (stored “memory” from prior turns).
   Then, produce your output, consisting of (a) updated reasoning and (b) rotation commands for the imagery module.
2. **Imagery module’s turn**: The module executes your commands, generates new images, and supplies them as context for the next iteration.

The question asks you to rotate the original to match the alternative, but it is the same to rotate the alternative to match the original. In this task, the imagery module will provide rotation capability of the alternatives, so that you have to match the original.

The **imagery module is stateful** — it preserves each object’s camera position between iterations.

> ⚠️ **Important:**
>
> * Each call to you represents **one iteration (one turn)** in the ongoing process.
> * **Do not simulate multiple turns** or the imagery module’s responses.
> * In each turn, **produce output**, then stop after returning a JSON object.

---

### Command System

**Valid targets:**
`A`, `B`, `C`

**Operations:**
`left`, `right`, `up`, `down`, `rotate:cw`, `rotate:ccw`

**Operation details:**

* `left`: rotate object left by the specified degree.
* `right`: rotate object right by the specified degree.
* `up`: tilt object upward by the specified degree.
* `down`: tilt object downward by the specified degree.
* `rotate:cw`: rotate object clockwise by the specified degree.
* `rotate:ccw`: rotate object counterclockwise by the specified degree.

Note: Rotation directions in the command are defined relative to the object, not the camera. As a result, they are the inverse of camera rotations. For example, `right:15` rotates the object 15° to the right. This is equivalent to **moving** the camera 15° to the left, or `yaw:-15`.

**Command syntax:**
Each command consists of the operation and degree separated by a colon.
Examples:

* `"left:15"`
* `"rotate:cw:30"`

**Rotation sequence syntax:**
A rotation sequence is a comma-separated list of commands applied in order.
Examples:

* `"left:15,right:15,up:15"`
* `"right:10,right:10,right:10"`

---

### Search Strategy & Logic (Think with Imagery)

You are an expert 3D analyst. Your goal is to prove whether the alternative (A, B, C) is the **same object** as the Original by finding a camera angle where they look **identical**.

**CRITICAL RULE: YOU MUST BE EXHAUSTIVE.**
LLMs tend to give up too early. You must not give up. You must not conclude "different" until you have viewed the object from all sides (Front, Back, Top, Bottom).

**Phase 1: Global Survey (The "Spin")**
*   If you have just started with an alternative, do not try to "guess" the match immediately. You likely have the wrong orientation.
*   **Action:** Send a command to rotate the object significantly to see multiple sides (e.g., `right:90, right:90, right:90`).
*   Gather visual data on the object's topology.

**Phase 2: Coarse Alignment**
*   Compare the "Survey" images with the Original. Look for specific landmarks (handles, holes, protrusions).
*   **Action:** Rotate the alternative to bring the matching landmark into roughly the same position.
*   **Correction Logic:**
    *   If the feature is too far to the left => command `right:X`.
    *   If the feature is too high => command `down:X`.
    *   **If the object looks "tilted" or "rotated" relative to the horizon** => You **MUST** use `rotate:cw` or `rotate:ccw` to align the roll. **Do not state "the angle is off" without issuing a command to fix it.**

**Phase 3: Fine Tuning & Verification**
*   Once roughly aligned, use small increments (`up:10`, `left:5`) to get a perfect lock.
*   **Proof of Match:** If you believe they are the same, you must generate a final **Proof Image** (a `left:0` command) where the two images are visually indistinguishable.

**Phase 4: Concluding**
*   **Matched:** Only mark as "matched" if you have generated the Proof Image.
*   **Not Matched:** Only mark as "not match" if you have completed Phase 1 (seen all sides) and Phase 2 (attempted alignment) and found irreconcilable geometric differences (e.g., "Original has a hole, Alternative does not").

---

### JSON Output Format

You must return a JSON object.
**IMPORTANT:** `final_answer` MUST remain `null` until you have completed the verification phase for all candidates.

```json
{
  "memory": {
    "iteration_count": integer,
    "current_target": "A|B|C",
    "search_phase": "Survey|Alignment|Verification|Finished",
    "visual_analysis": "Detailed comparison of landmarks. E.g., 'The handle is visible on the left in Original, but currently on the right in Alternative.'",
    "orientation_hypothesis": "E.g., 'I need to flip it 180 degrees horizontally and tilt it down 30 degrees.'",
    "status_log": {
       "A": "proven_match|proven_mismatch|investigating|waiting",
       "B": "...",
       "C": "..."
    }
  },
  "commands": [
    {
      "target": "A|B|C",
      "rotation_sequence": "string (e.g., 'right:90,right:90,right:90' or 'up:15,rotate:cw:10')"
    }
  ],
  "final_answer": "A|B|C|null"
}
```

### Constraints & Negative Constraints

1.  **NO EXCUSES:** Never say "the camera angle is slightly different" as a reason for mismatch. If the angle is different, **your job is to rotate the object to match that angle.**
2.  **STAY IN LOOP:** Do not output a `final_answer` in the first 3 turns of any specific alternative. You must gather data.
3.  **MANAGE TILT:** If the object matches but is "leaning," use `rotate:cw` or `rotate:ccw`.
4.  **EXHAUSTIVE:** If you cannot see the back of the object, you cannot conclude it doesn't match. You must rotate it.


""".strip()


prompt_gpt_5_2 = """

This task involves **visual 3D modeling and analysis** using an auxiliary tool called the **imagery module**.

Your job is to determine which alternative (**A, B, or C**) is the **odd one out** (i.e., **cannot** be rotated to match the original), using a **systematic, exhaustive rotation search** with the imagery module.

The imagery module can rotate objects and return snapshot images.

### Turn-based Interaction (IMPORTANT)
The interaction proceeds in **turns**:

1. **Your turn**: Analyze the provided images and the memory from prior turns. Then output:
   - Updated memory fields
   - Rotation commands for the imagery module
   - `final_answer` (only when allowed; see below)
2. **Imagery module’s turn**: Executes your commands and returns the resulting images in the next turn.

**Each call to you is exactly one turn.**
- **Do not simulate multiple turns**.
- **Return exactly one JSON object** and then stop.

The imagery module is **stateful**: each target keeps its current orientation across turns.

---

## Goal & Constraint
- Exactly **two** alternatives are **identical** to the original (matchable by rotation).
- Exactly **one** alternative is **not** identical (no rotation will match).
- Your goal is to find the odd one out.

**Hard rule:** Do **not** declare “probably_not_match” early. You must complete the required search coverage first.

---

## Command System

**Valid targets:** `A`, `B`, `C`  
**Operations:** `left`, `right`, `up`, `down`, `rotate:cw`, `rotate:ccw`

Directions are relative to the object (inverse of camera motion).

**Command syntax examples**
- `"left:15"`
- `"rotate:cw:30"`

**Rotation sequence**
- A comma-separated list of commands; one snapshot per step:
  - `"right:30,right:30,right:30"`

A `"left:0"` (or any `*:0`) produces a snapshot from the current view (no change).

---

## Output JSON Format (REQUIRED)
```json
{
  "memory": {
    "current_iteration": 1,
    "current_focusing_alternative": "A",
    "feedback_image_analysis": "",
    "match_status_updated": {
      "A": "unknown",
      "B": "unknown",
      "C": "unknown"
    },
    "next_to_focus_alternative": "A",
    "estimate_rotation_distance": ""
  },
  "commands": [
    {
      "target": "A",
      "rotation_sequence": "right:30,right:30"
    }
  ],
  "final_answer": null
}
```

---

## Matching Standard (strict)
An alternative is **matched** only if you can produce a view that is **visually indistinguishable** from the original with respect to:
- overall silhouette
- relative positions of protrusions/holes/notches
- distinctive edges/concavities
- any asymmetries

If you think it matches, you must obtain a **proof-of-match** snapshot (see below).

---

## Process Rules (systematic exhaustive search)

### 1) Work sequentially: A → B → C
Focus on one alternative per turn unless you have a good reason to issue commands to two in the same turn (generally avoid).

### 2) Required exhaustive coverage before “probably_not_match”
You may label an alternative `probably_not_match` **only after** completing **all** of the following minimum coverage for that alternative:

**Coverage plan (minimum):**
- **Yaw sweep:** 360° total, using 12 steps of 30° (e.g., `right:30` repeated 12 times), at a neutral pitch/roll as currently set.
- **Pitch sweep:** at least 120° total coverage (e.g., from roughly -60° to +60°), using 6 steps of 20° (either `up:20` or `down:20` as needed across turns).
- **Roll sweep:** 360° total, using 12 steps of 30° (`rotate:cw:30` repeated 12 times), at a promising yaw/pitch.

Because each assistant call is one turn, you can distribute these sweeps across multiple turns. Track progress in memory (in text).

**Minimum turns rule (hard):**
- You must spend **at least 3 turns per alternative** before you are allowed to set it to `probably_not_match`, **even if it looks wrong early**.

### 3) Two-phase strategy
- **Phase A (coarse scan):** Run a large sweep (e.g., yaw 360°) to discover whether any viewpoint strongly resembles the original.
- **Phase B (refinement):** Once a promising view appears, use smaller steps (5°–15°) to converge.

### 4) Proof-of-match requirement (hard)
If you conclude an alternative matches:
1. Mark it as `matched` **only after** you have found a near-identical view during refinement.
2. Then, on the **next turn**, request **one no-rotation snapshot** (e.g., `"left:0"`) to record the stable matching view as **PROOF OF MATCH**.

### 5) Hard prohibition on early final answer
You may set `final_answer` only if:
- You have **proof-of-match** snapshots for **two** alternatives (`matched`), AND
- The remaining one has either:
  - completed the minimum coverage and is `probably_not_match`, or
  - it is logically forced as the odd one out because the other two are proven matched.

Until then, `final_answer` must be `null`.

### 6) Don’t use vague stopping reasons
Avoid statements like “tilt/yaw is off” as a conclusion. Instead:
- treat misalignment as a cue to continue the sweep/refinement,
- specify the next concrete rotation plan (what axis, direction, degrees, how many steps).

### 7) If uncertainty persists, intensify search
If after completing A/B/C once you still can’t identify the odd one:
- revisit the most ambiguous ones,
- run additional sweeps with different pitch baselines (e.g., pitch down 30°, then yaw sweep again),
- use `left:0` snapshots to re-check current orientation.

**DON’T GIVE UP.** Continue until the criteria for final_answer are met.

---

## What to store in `memory.feedback_image_analysis`
Each turn, describe:
- what changed across the returned snapshot sequence,
- which snapshot index looked closest to the original and why,
- what axis misalignment remains (yaw vs pitch vs roll),
- what next sweep/refinement step you will do.

Also update:
- match statuses
- next target to focus

""".strip()


prompt_gemini_new = """
# Role: Autonomous 3D Visual Search Engine

You are an expert in Spatial Reasoning and Visual Analysis. Your task is to solve a "Find the Odd One Out" puzzle by comparing a **Reference Object** (Original) against three **Alternatives** (A, B, C).

Two of the alternatives are identical to the Original (just rotated). One is different.
Your goal is to control an **Imagery Module** to rotate the alternatives until you find the matching angle for two of them, thereby identifying the non-matching one.

---

## ⚙️ The Imagery Module & Interaction Loop

You interact with a stateful tool. You do not see the whole execution at once. You output commands, the system rotates the object, generates snapshots, and calls you back.

**The Loop:**
1.  **Input:** You receive the current view of A, B, and C.
2.  **Action:** You analyze the images and output a **rotation plan** for the *next* step.
3.  **System:** Executes your commands and feeds the new images back to you in the next prompt.

**CRITICAL CONSTRAINTS:**
1.  **NEVER** simulate the next turn. Output commands for the *current* turn only.
2.  **NEVER** give up early. You must perform a **Systematic Exhaustive Search** before concluding a mismatch.
3.  **NEVER** set `final_answer` in the first few turns. Deep search is required.
4.  **Persistence:** If an object looks "almost" right but the camera tilt/yaw is slightly off, **DO NOT** conclude it is different. Instead, issue the specific rotation command (e.g., `up:10`, `rotate:cw:5`) to align them perfectly.

---

## 📡 Search Protocols (How to behave)

Do not simply "guess." Follow these phases for *each* alternative until a match is confirmed or the search is fully exhausted.

### Phase 1: Global Yaw Sweep (Coarse Search)
If you do not see a match yet, you must rotate the object 360° horizontally to check all sides.
*   **Command Strategy:** Use chained commands to get multiple views in one turn.
*   *Example:* `"right:45,right:45,right:45,right:45"` (Covers 180 degrees in one turn with 4 snapshots).

### Phase 2: Vertical & Roll Check (Deep Search)
If the 360° yaw sweep fails, the object might be tilted.
*   Change the pitch (`up`/`down`) or roll (`rotate:cw`) significantly (e.g., 90 degrees) and repeat the Yaw Sweep.
*   *Rule:* You cannot mark "probably_not_match" until you have attempted at least **3 different pitch/roll orientations** combined with yaw sweeps.

### Phase 3: Fine-Tuning (The "Lock In")
Once you see a potential match (features align but angle is wrong):
*   Switch to small increments: `right:5`, `up:5`, `rotate:cw:5`.
*   Goal: Align the internal features, protrusions, and holes exactly with the Original.

### Phase 4: Proof of Match
You generally cannot declare a match based on a rotating image. You must pause to verify.
*   **Required Action:** Before setting an alternative to `"matched"`, you must execute a specific command: `"left:0"` (no movement).
*   This generates a clean, static snapshot. If this static snapshot matches the Original, **then** you mark it as `"matched"`.

---

## 🎮 Command Syntax

**Targets:** `A`, `B`, `C`
**Operations:** `left`, `right`, `up`, `down`, `rotate:cw` (roll), `rotate:ccw` (roll).
**Format:** `operation:degrees`
**Chaining:** `op:deg,op:deg,op:deg` (Comma separated).

**Examples:**
*   *Search Mode:* `"right:60,right:60,right:60"` (Big jumps to find the view).
*   *Fixing Tilt:* `"up:15,rotate:cw:10"` (Correcting camera angle).
*   *Verification:* `"left:0"` (Snapshot for proof).

---

## 📝 Output Format (JSON Only)

You must return a single JSON object.

```json
{
  "memory": {
    "current_iteration": 1,
    "analysis_of_previous_turn": "Detailed visual comparison. E.g., 'Alternative A has the hole on the left, but Original has it on the right. I need to rotate A 180 degrees.'",
    "search_status": {
      "A": "Phase 1: Yaw Sweep" | "Phase 3: Fine Tuning" | "Matched" | "Exhausted",
      "B": "Waiting",
      "C": "Waiting"
    },
    "reasoning_for_next_action": "Explain why you are choosing the specific commands below."
  },
  "commands": [
    {
      "target": "A",
      "rotation_sequence": "right:45,right:45,right:45"
    }
  ],
  "final_answer": "A" | "B" | "C" | null
}
```

**Rules for `final_answer`:**
1.  **Default to `null`**. You are expected to run for multiple iterations (5+).
2.  **Only** output "A", "B", or "C" if:
    *   You have successfully confirmed matches for **two** alternatives (with Proof of Match snapshots).
    *   You have exhaustively searched the third one and confirmed it cannot match.
3.  **Tie-breaker:** If `current_iteration` > 15 and you still haven't found the solution, output the most likely candidate based on evidence, but prefer `null` if unsure.

---

## 🧠 Mental Checklist for Current Turn:
1.  Did I rotate A/B/C enough? If I only rotated 45 degrees so far, I cannot conclude anything.
2.  Is the camera tilted? If yes, send `up`/`down`/`rotate` commands to fix it. **Do not complain that it is off.**
3.  Does the snapshot look identical? If yes, issue `left:0` to confirm.
4.  Do I have proof for 2 matches? If no, `final_answer` is `null`.

""".strip()

prompt_claude = """

## Visual 3D Object Matching Task

### Overview
You are an AI agent that must identify which 3D object (A, B, or C) differs from the original through systematic visual comparison. You will interact with an **imagery module** that can rotate objects and capture snapshots.

**Core Constraint**: Exactly TWO alternatives can be rotated to match the original view. ONE cannot match regardless of rotation.

### Interaction Protocol

The system operates in **iterative turns**:

1. **Your turn**: Analyze provided images and memory state, then output rotation commands
2. **Imagery module's turn**: Executes commands, returns snapshot images
3. **Repeat** until you set `final_answer`

> ⚠️ **Critical Rules:**
> - Each call = one iteration only
> - The system will call you repeatedly until task completion
> - Never simulate multiple turns in one response
> - The imagery module maintains object rotation state between calls

---

### Command System

**Targets**: `A`, `B`, `C`

**Operations** (relative to object, not camera):
- `left:degrees` - rotate object left
- `right:degrees` - rotate object right  
- `up:degrees` - tilt object up
- `down:degrees` - tilt object down
- `rotate:cw:degrees` - rotate clockwise (roll)
- `rotate:ccw:degrees` - rotate counterclockwise (roll)

**Syntax Examples**:
- Single: `"left:30"`
- Sequence: `"right:30,up:15,rotate:cw:45"`
- Snapshot only: `"left:0"` (captures current position)

---

### Mandatory Search Protocol

You MUST follow this systematic search pattern for EACH alternative:

#### Phase 1: Initial Sweep (Iterations 1-4 per alternative)
- **Iteration 1**: Yaw sweep - `"right:30,right:30,right:30,right:30,right:30,right:30,right:30,right:30,right:30,right:30,right:30,right:30"` (full 360°)
- **Iteration 2**: Pitch sweep - `"up:30,up:30,up:30,down:30,down:30,down:30,down:30,down:30,down:30"` (±90°)
- **Iteration 3**: Roll sweep - `"rotate:cw:30,rotate:cw:30,rotate:cw:30,rotate:cw:30,rotate:cw:30,rotate:cw:30,rotate:cw:30,rotate:cw:30,rotate:cw:30,rotate:cw:30,rotate:cw:30,rotate:cw:30"` (full 360°)
- **Iteration 4**: Return to promising angle from sweeps

#### Phase 2: Refinement (Iterations 5-8 per alternative)
- Fine-tune with 5-10° increments around best candidate orientation
- If match found, proceed to Phase 3
- If no match after 8 iterations, mark as `probably_not_match`

#### Phase 3: Proof Generation (1 additional iteration)
- For matched alternatives: Generate proof snapshot with `"left:0"`
- Image must show exact visual alignment with original

---

### Output Format

```json
{
  "memory": {
    "current_iteration": integer,
    "global_iteration_count": integer,
    "current_alternative": "A|B|C",
    "phase": "sweep|refine|proof",
    "iterations_per_alternative": {
      "A": integer,
      "B": integer,
      "C": integer
    },
    "match_status": {
      "A": "unknown|searching|matched|probably_not_match",
      "B": "unknown|searching|matched|probably_not_match",
      "C": "unknown|searching|matched|probably_not_match"
    },
    "proof_images_generated": {
      "A": boolean,
      "B": boolean,
      "C": boolean
    },
    "image_analysis": "Detailed analysis of current snapshots",
    "next_rotation_rationale": "Explanation for next command choice"
  },
  "commands": [
    {
      "target": "A|B|C",
      "rotation_sequence": "command:degrees,..."
    }
  ],
  "final_answer": null | "A|B|C"
}
```

---

### Mandatory Constraints

1. **Minimum Iterations Rule**: You MUST perform at least 8 iterations per alternative before marking as `probably_not_match`

2. **No Early Termination**: You CANNOT set `final_answer` until:
   - All three alternatives have been searched (minimum 8 iterations each)
   - Exactly two alternatives are marked `matched` with proof images
   - Exactly one alternative is marked `probably_not_match`

3. **Proof Requirement**: An alternative is only considered `matched` when:
   - You've found an orientation visually identical to the original
   - You've generated a proof snapshot showing the match

4. **Visual Grounding**: Every decision must reference specific visual features:
   - Shape alignment
   - Edge correspondence  
   - Surface details
   - Shadow/lighting consistency

---

### Search Strategy

1. **Never skip the systematic sweep** - even if you think you see a match early
2. **Document visual landmarks** - identify specific features to track during rotation
3. **Compare incrementally** - use each snapshot to guide the next rotation
4. **Persist through ambiguity** - if all seem to match/not match, increase search resolution
5. **Validate thoroughly** - a match requires perfect visual correspondence, not just similarity

### Remember
- The system will keep calling you until you provide `final_answer`
- You must exhaust the search space before concluding
- Two alternatives WILL match by rotation; one WILL NOT
- Visual evidence is required - speculation is not sufficient

""".strip()

reasoner_with_answer = reasoner_with_answer_ORG

reasoner_for_final_answer = """
For this visual problem, generate the answer in the following json format:
```json
{
  "force_stop": true,
  "final_answer": "Your answer to the visual problem",
}
```
"""


class ResponseWithoutAnswer(BaseModel):
    rationale: str
    rotation_sequence: str


class TargetAndCommand(BaseModel):
    target: str
    rotation_sequence: str


class ResponseWithAnswer(BaseModel):
    final_answer: str
    rationale: str
    commands: list[TargetAndCommand]


def rationale_with_imagery_response(rationales, imagery_images):
    # ensure that rationale and imagery response are in the same length
    assert len(rationales) == len(
        imagery_images
    ), "Rationale and imagery response must be in the same length"

    rationale_with_imagery_resonse = []
    for i in range(len(rationales)):
        rationale_with_imagery_resonse.append(rationales[i])
        # for image, include only the last 3 images
        if i >= len(imagery_images) - 1:
            for image_url, content in imagery_images[i]:
                rationale_with_imagery_resonse.append(
                    dict(
                        # role="assistant",
                        role="user",  # gpt 5.2 not support assistant role for image content
                        content=content,
                        image_url=image_url,
                    )
                )
    return rationale_with_imagery_resonse


def rationale_with_imagery_response_last_3_only(rationales, imagery_images):
    """
    This version pass throuth only the last 3 iterarations
    """
    # ensure that rationale and imagery response are in the same length
    assert len(rationales) == len(
        imagery_images
    ), "Rationale and imagery response must be in the same length"

    rationales = rationales[-2:]
    imagery_images = imagery_images[-2:]

    rationale_with_imagery_resonse = []
    for i in range(len(rationales)):
        rationale_with_imagery_resonse.append(rationales[i])
        # if i >= len(imagery_images) - 1:   #include only the last 1 iteration image
        for image_url, content in imagery_images[i]:
            rationale_with_imagery_resonse.append(
                dict(
                    # role="assistant",
                    role="user",  # gpt 5.2 not support assistant role for image content
                    content=content,
                    image_url=image_url,
                )
            )
    return rationale_with_imagery_resonse


def invalid(cmd_string):
    # Valid command format: "yaw:10,pitch:30,roll:-10"
    allowed_commands = {"left", "right", "up", "down", "rotate"}
    if not isinstance(cmd_string, str):
        return True
    cmds = [cmd.strip() for cmd in cmd_string.split(",") if cmd.strip()]
    if not cmds:
        return True
    for cmd in cmds:
        if ":" not in cmd:
            return True
        command, value = cmd.split(":", 1)
        if command.strip().lower() not in allowed_commands:
            return True
        # if command != "reset":
        #     try:
        #         float(value)
        #     except Exception:
        #         traceback.print_exc()
        #         return True
        # else:
        #     if value not in ["x", "y", "z", "iso"]:
        #         return True
    return False


class ToolsBackedImageryReasoner_Eval_08101:

    # REASONING_MODEL = 'chatgpt-4o-latest'
    # REASONING_MODEL = 'gpt-5.1-chat-latest'
    # REASONING_MODEL = 'gpt-5.2-chat-latest'
    # REASONING_MODEL = "gpt-5.2"
    REASONING_MODEL = "gemini-3-flash-preview"

    @classmethod
    async def reason_loop(
        cls,
        chat_message: ChatMessage,
        model: str | ModelWithParameters,
        options=None,
        save_raw=True,
    ):

        model_name = cls.REASONING_MODEL

        async def call_llm(history, model_name, options):
            print(
                f"\n------------------------->>>\ncall_llm {model_name}:>>>",
                json.dumps(history, indent=2, cls=CustomJSONEncoder),
            )
            _answer, _image_url, _files, _meta = await AnyModel().chat(
                history, model_name, options
            )
            if save_raw:
                chat_history.append(
                    dict(
                        role="assistant",
                        content=_answer,
                        image_url=_image_url,
                        files=_files,
                        meta=_meta,
                        created_at=get_now(),
                        persist=True,
                    )
                )
            _meta = _meta if isinstance(_meta, dict) else _meta.model_dump()
            output = _meta.get("output") or _answer
            print(
                f"\n-------------------------<<<\ncall_llm {model_name}:<<<",
                json.dumps(output, indent=2, cls=CustomJSONEncoder),
            )
            return _answer, _image_url, _files, _meta

        def get_now():
            nonlocal datetime_incrementer
            datetime_incrementer += 1000
            return (
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.datetime.resolution * datetime_incrementer
            )

        # --- main body ---
        datetime_incrementer = 0
        bounds_map = chat_message.imagery_args["bounds_map"]
        # foundation_image_url = chat_message.imagery_args['foundation_image_url']

        # create the stateful imagery model
        imagery = StatefulImageryWithInitialRotationModule_8(
            bounds_map, off_screen=True, show_grid=False
        )
        try:

            # question image and question
            chat_history = [
                dict(
                    role="user",
                    file_url=chat_message.imagery_args["question_image_url"],
                    file_name=chat_message.imagery_args["question_file_name"],
                    content_type="image/png",
                    created_at=get_now(),
                    id=None,
                    persist=True,
                ),
                dict(
                    role="user",
                    content=chat_message.message,
                    created_at=get_now(),
                    id=None,
                    persist=True,
                ),
            ]

            freeze_history = chat_history[
                :
            ]  # history holds the history for this interation only

            MAX_ITERATION = 20
            iter_count = 1

            rationales = []
            imagery_images = []
            while iter_count <= MAX_ITERATION:

                # call reasoner module with imagery module aware prompt, and last image if exists
                print(
                    f"\n=================== Call REASONING model {iter_count} ==================\n"
                )

                # if iter_count <= MIN_ITERATION:
                #     reasoner_system_message = reasoner_with_answer
                #     response_schema = ResponseWithoutAnswer.model_json_schema()
                # else:
                reasoner_system_message = reasoner_with_answer
                # response_schema = ResponseWithAnswer.model_json_schema()

                reasoning_retry_cout = 5
                valid = False
                while reasoning_retry_cout > 0:
                    reasoning_retry_cout -= 1
                    response, _, _, _ = await call_llm(
                        [{"role": "system", "content": reasoner_system_message}]
                        + freeze_history
                        + rationale_with_imagery_response(rationales, imagery_images),
                        model_name,
                        options={
                            "response_mime_type": "application/json",
                            # "response_json_schema": response_schema,
                        },
                    )

                    response_dict = parser_json(response)
                    if not isinstance(response_dict, dict):
                        print(f"Not a dictionary. RETRY {reasoning_retry_cout}")
                        continue

                    final_answer = response_dict.get("final_answer")
                    commands = response_dict.get("commands")
                    if final_answer and not commands:
                        print('"final_answer" found, no commands provided. Finish')
                        return final_answer, chat_history, None
                    if not commands:
                        print(
                            f"No commands found. RETRY {reasoning_retry_cout} {response} "
                        )
                        continue

                    # no final answer, valid rotation sequence. Valid output!
                    valid = True
                    break

                if not valid:
                    # handle as the model has answered 'None', and finish
                    return "None", chat_history, None

                # -- continues iteration --
                # build history for reasoning
                rationales.append({"role": "assistant", "content": response})

                # join same target commands
                commands_map = {}
                for command in commands:
                    target = command.get("target")
                    if target.lower() == "original":  # fix 'Original' to 'original'
                        target = "original"
                    if target not in commands_map:
                        commands_map[target] = []
                    commands_map[target].append(command.get("rotation_sequence"))
                for target, commands in commands_map.items():
                    commands_map[target] = ",".join(commands_map[target])

                command_images = []
                for target, commands in commands_map.items():
                    # call imagery
                    print(
                        f"\n==[{cls.__name__}]================= Call IMAGERY {target} {commands} ==================\n"
                    )
                    image_path = imagery.run_human_sequence_and_save_image(
                        target, commands
                    )
                    print(f"==[{cls.__name__}] image_path: [{image_path}]: <<")
                    if image_path:  # OK

                        # read image bytes
                        with open(image_path, "rb") as f:
                            file_content = f.read()

                        # upload to S3
                        image_url = await S3UploadServices.upload_generate_image(
                            Path(image_path).name,
                            file_content,
                            Path(image_path).suffix.lstrip("."),
                            FileCategory.GENERATED,
                        )
                        print(f"image_url: [{image_url}]: <<")
                        if not image_url:
                            raise Exception(f"Error uploading file to S3 {image_path}")
                        else:
                            # await wait for 10 seconds
                            await asyncio.sleep(10)

                        content = f"[image generated by Imagery Module {imagery.__class__.__name__}] for target {target} and rotation sequence {commands}"
                        if save_raw:
                            chat_history.append(
                                dict(
                                    role="user",
                                    content=content,
                                    image_url=image_url,
                                    created_at=get_now(),
                                    persist=True,
                                )
                            )

                        command_images.append((image_url, content))

                    else:
                        raise Exception(f"Image not generated {response}")

                # imagery history
                imagery_images.append(command_images)

                iter_count += 1

            # exceed iterations, call without system message
            print(
                f"\n=={cls.__name__}================= Exceeded MAX. Reasoning model LAST call ==================\n"
            )
            response, _, _, _ = await call_llm(
                [{"role": "system", "content": reasoner_for_final_answer}]
                + freeze_history
                + rationale_with_imagery_response(rationales, imagery_images),
                cls.REASONING_MODEL,
                options,
            )

            response_dict = parser_json(response)
            return response_dict.get("final_answer", response), chat_history, None

        finally:
            imagery.close()
