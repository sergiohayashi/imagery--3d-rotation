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


prompt_OLD = """
# TASK AND ITERATIVE PROCESS
Your task is to solve a 3D visual matching problem in conjunction with an auxiliary tool called the imagery module.

The imagery module maintains a stateful representation of the 3D objects in the problem. It can manipulate (rotate) an object and generate a snapshot from the most recent camera angle. 

This is an iterative process. The iteration is controlled externally. In you turn, make the necessary analysis, and finish you turn by generating the output as specified below.

In each turn, you can generate one sequence of rotation commands for one or more targets. Then, the imagery module (controlled externally) will apply the commands and return a snapshot image after each command.

Valid targets are "A", "B", and "C".
Valid commands are: `left`, `right`, `up`, `down`, `rotate:cw`, and `rotate:ccw`.
These commands rotate the object (i.e., the inverse of moving the camera).
Rotations are relative to the camera angle (camera-space rotation).
The command`rotate:cw` rotates clockwise; `rotate:ccw` rotates counterclockwise.

Commands are followed by an angle. For example, `left:30` rotates the target object by 30 degrees.
Valid sequence examples: `left:30,right:30,up:30`, `left:0,rotate:ccw:90,rotate:cw:90`.
Each command will generate a snapshot image.
Rotation with value (0) generate the current state snapshot image.

# OUTPUT
At the end of each iteration (i.e., at the end of your turn), generate output in JSON format as follows:
```json
{
  "memory": {
    "rationale": "your rationale so far",
    "iteration_number": integer (e.g., 1, 2, 3...),
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

- `commands` is a list. Each element targets one object and may contain one or more commands, as in the example.
- `final_answer` is the final answer. Fill this field only when you have the final answer; this will terminate the iterative process. Otherwise, set it to `null`.
- `iteration_number`: set `1` for the first turn and increment by one thereafter.

# CONTEXT
All previous outputs will be provided in the context.
Only the most recent command output image (one for each requested target) will be provided.

# RULES
- Run at least 3 iterations. Give the final answer only from the 3rd iteration, NOT before.

"""


prompt_with_reset = """
# TASK AND ITERATIVE PROCESS
Your task is to solve a 3D visual matching problem using an auxiliary imagery module.

The module is stateful: each new command continues from the last view of that target.  
In each turn, you may send one rotation sequence per target ("A", "B", "C").  
The system returns snapshots after each command in the sequence.

Interpret commands by their **visual object effect** (as if rotating the object by hand):

- `left:<deg>`: object turns left
- `right:<deg>`: object turns right
- `up:<deg>`: object turns upward
- `down:<deg>`: object turns downward
- `rotate:cw:<deg>`: object spins clockwise in the image plane
- `rotate:ccw:<deg>`: object spins counter-clockwise in the image plane
- `view:x|y|z|iso`: reset to a canonical viewpoint

Examples:
- `right:30,up:20`
- `view:iso,left:45,rotate:cw:90`
- `left:0` (no movement, just snapshot of current state)

# OUTPUT
Return JSON exactly in this format:
```json
{
  "memory": {
    "rationale": "your rationale so far",
    "iteration_number": 1
  },
  "commands": [
    {
      "target": "A",
      "rotation_sequence": "right:15,right:15,up:10"
    }
  ],
  "final_answer": null
}
```

- `commands`: list of per-target command sequences.
- `final_answer`: `"A"`, `"B"`, `"C"`, or `null`. Use non-null only when done.
- `iteration_number`: start at 1, increment each turn.

# CONTEXT
Previous outputs are provided.  
Only the most recent command output image(s) are provided.

# RULES
- Run at least 3 iterations.
- Do not provide `final_answer` before iteration 3.
"""


prompt_prev = """
# TASK AND ITERATIVE PROCESS

Your task is to resolve a 3D model rotation problem.

The problem is given as the following statement, along with an image:
`The left image shows the original cube stack made of equal-sized small cubes. Which of the options on the right cannot be obtained by rotating the original cube stack? Please answer from options A, B, or C.`

# IMAGERY MODULE

To resolve the problem, you will have access to an auxiliary tool called the imagery module.

The imagery module maintains a stateful 3D representation of the objects in the problem. It can manipulate (rotate) an object and generate a snapshot from the current camera perspective. The initial state exactly matches the camera angle of the objects as shown in the problem statement.

The problem involves determining whether one object is the same as another except for the camera angle. This requires rotating the object until it has the same visual appearance as the target object. The imagery module helps by actually applying the rotations and generating a visual snapshot after each rotation, from which you can verify the match simply by comparing the equivalence of two static images. Note also that the problem asks whether rotating the original can produce the alternative, but this is equivalent to rotating the alternative to obtain the original. The imagery module only allows rotating the alternative.

Generating the snapshot image of the angle that make them the same is a clear evidence that the objects are the same. 

Working with the imagery module is an iterative process. The iteration is controlled externally. In your turn, make the necessary analysis, and finish your turn by generating the output as specified below.

In each turn, you can generate one sequence of rotation commands for one or more targets. Then, the imagery module (controlled externally) will apply the commands, change the state of the objects, and return a snapshot image after each command.

The rotation commands can be interpreted object rotations in camera space. Intuitively, it will look as if rotating the object holding in your hands. When you rotate to `right` it will have the effect of the object rotated to the `right` in your hands, that is equivalent to move the camera (your eyes) to the left, in orbital movement, centralized to the object, maintaing the same distance to the object. The commands are:

- `left:<deg>`: object turns left
- `right:<deg>`: object turns right
- `up:<deg>`: object turns upward
- `down:<deg>`: object turns downward
- `rotate:cw:<deg>`: object spins clockwise in the image plane
- `rotate:ccw:<deg>`: object spins counter-clockwise in the image plane

`<deg>` is the rotation angle. The value of 0 will generate the current state snapshot (not rotation applied).

Example:
`right:0,right:30,up:20`: This command generates 3 snapshots. First, get the snapshot from the current state, then rotate to the right by 30 degrees and take another snapshot, and then rotate up by 20 degrees and take another snapshot. The resulting image is a grid with 3 snapshot of the object.
Note that degree of 0 only make sense as the first rotation command, because in other positions it will only repeat the same snapshot.

# OUTPUT
Return JSON exactly in this format:
```json
{
  "memory": {
    "rationale": "your rationale so far",
    "iteration_number": 1,
    "partial_conclusion": {
      "A": "unknown"|"probably_not_the_answer"|"probably_the_odd_one",
      "B": "unknown"|"probably_not_the_answer"|"probably_the_odd_one",
      "C": "unknown"|"probably_not_the_answer"|"probably_the_odd_one",
    }
  },
  "commands": [
    {
      "target": "A|B|C",
      "rotation_sequence": "right:15,right:15,up:10"
    }
  ],
  "final_answer": null
}
```

- `commands`: list of per-target command sequences.
- `final_answer`: `"A"`, `"B"`, `"C"`, or `null`. Use non-null only when done.
- `iteration_number`: start at 1, increment each turn.

# CONTEXT
- All the previous outputs, including memory, are provided in each turn.  
- Only the most recent (last turn) command output image(s) are provided.
- The problem statement and image are always provided.
- The image of the original object is always provided.

# RULES
- Run at least 3 iterations. More than 5 is prefereable
- Do not provide `final_answer` before you have the final conclusion.
- 

"""

prompt__pt = """
# TAREFA E PROCESSO ITERATIVO

Sua tarefa é resolver um problema de rotação de modelo 3D.

O problema inclui uma imagem com 4 figuras, e a seguinte declaração:
`A imagem à esquerda mostra a pilha de cubos original feita de pequenos cubos de tamanhos iguais. Qual das opções à direita não pode ser obtida girando a pilha de cubos original? Responda usando as opções A, B ou C.`

# MÓDULO DE IMAGENS

Para resolver este problema, você vai trabalhar em conjunto com uma ferramenta chamada módulo de imagens.

O módulo de imagens mantém uma representação 3D dos objetos do problema, e sabe executar operações de rotação, e gerar snapshots (imagem) correspondente ao estado atual (i.e, ângulo de câmera). O estado de cada objeto é mantido durante o processo inteiro. O estado inicial (ângulo de câmera) de cada objeto corresponde à imagem na declaração do problema.

O objetivo da tarefa é verificar se um objeto pode ser rotacionado para obter a mesma visão de uma das alternativas. Para os problemas em questão isso é equivalente a rotacionar as alternativas, para obter a visão da original.

O imagery module permite rotacionar somente as alternativas. O imagery module ajuda a resolver o problema permitindo rotacionar de fato os objetos e obter o snapshot do estado corrente, de tal forma que a validação possa ser feita por simples comparação da imagem, ao final da rotação.

O trabalho com o módulo de imagems é um processo iterativo, controlado extenamente. Na sua vez, faça a anaĺise necessária baseado nas imagens providas, e gere ao final um conjunto de rotação a realizar. O módulo de imagens irá então aplicar estas rotações, e retornar uma nova imagem, correspondente ao novo estado do objeto.

Os comandos de rotação são referentes ao objeto (objeto é rotacionado), no espaço da câmera. Intuitivamente, é a visão que uma pessoa teria, quando manipula o objeto em suas mãos. É um movimento orbital, centrado no objeto, com a distância fixa.

Os comandos possíveis são:
- `left:value` (objeto é rotacionado para a esquerda)
- `right:value` (objeto é rotacionado para a direita)
- `up:value` (objeto é rotacionado para cima)
- `down:value` (objeto é rotacionado para baixo)
- `rotate:cw:value` (objeto gira no sentido horário no plano da imagem)
- `rotate:ccw:value` (objeto gira no sentido anti-horário no plano da imagem)

`value` refere-se ao ângulo de rotação em grauis. Ângulo 0 também é válido, e gera um snapshot do estado atual.

Exemplo de sequência de comandos: `right:0,right:30,up:20`
Nesse exemplo, inicialmente é feito uma rotação de valor 0, o que significa que o objeto não mexe, e é gerado um snapshot do estado atual. Em seguida, é aplicado uma rotação para a direita (equivalente à camera girar para a esquerda), e é gerado novamente um snapshot. Ao final, é feito uma rotação para cima, e gerado novamente um snapshot. O resutado é uma imagem em grid contendo estas 3 imagens pós-rotação.

# SAÍDA

Retorne sua resposta em formato JSON, conforme o formato a seguir:

```json
{
  "memory": {
    "rationale": "sua justificativa até o momento",
    "partial_conclusion": {
      "A": "unknown"|"probably_not_the_answer"|"probably_the_odd_one",
      "B": "unknown"|"probably_not_the_answer"|"probably_the_odd_one",
      "C": "unknown"|"probably_not_the_answer"|"probably_the_odd_one"
    }
  },
  "iteration_number": 1,
  "commands": [
    {
      "target": "A"|"B"|"C",
      "rotation_sequence": "right:15,right:15,up:10"
    }
  ],
  "final_answer": null
}
```

Detalhes dos campos de saída:
- `memory`: A sua `memória` de reasoning. Todo o histórico de memória é provido no contexto da iteração.
- `commands`: Sequência de rotações, para um ou mais objetos target.
- `final_answer`: Responta final, caso tenha a resposta definitiva. Caso contrário, deixar como null.
- `iteration_number`: Contador de iterações. Inicie com 1 e incremente este número em cada turno.

# CONTEXTO

O contexto da convers, provided in each turn, inclui:
- Todas as saídas geradas anteriormente, incluindo o campo `memory`.
- Das imagens geradas pelo imagery module, apenas as da última iteração.
- O texto e a imagem, do enunciado do problema.
- O imagem do `original` será sempre provido nas iterações.

# ESTRATÉGIA

- Executar pelo menos 5 iterações, antes de dar a resposta final.
"""

prompt_p20260306_01 = """
# TASK AND ITERATIVE PROCESS

Your task is to solve a 3D model rotation problem.

The problem includes an image with 4 figures, and the following statement:
`The left image shows the original cube stack made of equal-sized small cubes. Which of the options on the right cannot be obtained by rotating the original cube stack? Please answer from options A, B or C.`

# IMAGE MODULE

To solve this problem, you will work together with a tool called the image module.

The image module maintains a 3D representation of the problem objects and knows how to perform rotation operations and generate snapshots (images) corresponding to the current state (i.e., camera angle). The state of each object is maintained throughout the entire process. The initial state (camera angle) of each object corresponds to the image in the problem statement.

The goal of the task is to verify whether an object can be rotated to obtain the same view as one of the alternatives. For the problems in question, this is equivalent to rotating the alternatives to obtain the view of the original.

The image module allows rotating only the alternatives. The image module helps solve the problem by actually rotating the objects and obtaining a snapshot of the current state, reducing this way, the validation step to a more simple image comparison.

Working with the image module is an iterative process, controlled externally. On your turn, perform the necessary analysis based on the provided images, and at the end generate a set of rotations to perform. The image module will then apply these rotations and return a new image corresponding to the new state of the object.

The rotation occurs in object space (i.e., the object itself rotates relative to the camera). Intuitively, this matches the view of manipulating an object in your hands: the object spins around its center while the camera (your viewpoint) remains fixed.

The possible rotation commands are:
- `left:value` (object is rotated to left)
- `right:value` (object is rotated to right)
- `up:value` (object is rotated up)
- `down:value` (object is rotated down)
- `rotate:cw:value` (object rotates clockwise in the image plane)
- `rotate:ccw:value` (object rotates counterclockwise in the image plane)

`value` refers to the rotation angle in degrees. Angle 0 is also valid and generates a snapshot of the current state.

Example sequence of commands: `right:0,right:30,up:20`
In this example, initially a rotation of value 0 is performed, meaning the object does not move, consequently a snapshot of the current state is generated. Then, a rotation to the right is applied (equivalent to the camera rotating to the left), and a snapshot is generated again. Finally, a rotation up is performed, and a snapshot is generated again. The result is a grid image containing these 3 post-rotation images.

# OUTPUT

Return your response in JSON format, following the format below:

```json
{
  "memory": {
    "rationale": "your justification up to this point",
    "partial_conclusion": {
      "A": "unknown"|"probably_not_the_answer"|"probably_the_odd_one",
      "B": "unknown"|"probably_not_the_answer"|"probably_the_odd_one",
      "C": "unknown"|"probably_not_the_answer"|"probably_the_odd_one"
    }
  },
  "iteration_number": 1,
  "commands": [
    {
      "target": "A"|"B"|"C",
      "rotation_sequence": "right:15,right:15,up:10"
    }
  ],
  "final_answer": null
}
```

Details of the output fields:
- `memory`: Your `memory` of reasoning. The entire memory history is provided in the iteration context.
- `commands`: Sequence of rotations, for one or more target objects.
- `final_answer`: Final response, if you have the definitive answer. Otherwise, leave as null.
- `iteration_number`: Iteration counter. Start with 1 and increment this number each turn.

# CONTEXT

The conversation context, provided in each turn, includes:
- All previously generated outputs, including the `memory` field.
- From the images generated by the image module, only those from the last iteration.
- The text and image from the problem statement.
- The `original` image will always be provided in the iterations.

# STRATEGY

- Perform at least 5 iterations before giving the final answer.

```

Details of the output fields:
- `memory`: Your `memory` to help in the decision-making process. 
- `commands`: Sequence of rotation commands, for one or more target objects.
- `final_answer`: The alternative label if have reached a definitive answer, or null otherwise.
- `iteration_number`: Iteration counter. Start with 1 and increment this number in each turn.

# CONTEXT

The conversation context, provided in each iteration, will include:
- The text and the image of the problem statement.
- All you previous `output`, including the `memory` field.
- The images generate by the imagery, of the last turn only.
- The image of the `original` will always be provided, to help comparison.

# RULE

- Execute at least 5 iterations before your final answer.


"""

# o gpt-5.4 simula sozinho
prompt_p20260306_02 = """
# TASK AND ITERATIVE PROCESS

Your task is to solve a 3D model rotation problem.

The problem includes an image with 4 figures, and the following statement:
`The left image shows the original cube stack made of equal-sized small cubes. Which of the options on the right cannot be obtained by rotating the original cube stack? Please answer from options A, B or C.`

# IMAGE MODULE

To solve this problem, you will work together with a tool called the imagery module.

The imagery module maintains a 3D representation of the problem objects and knows how to perform rotation operations and generate snapshots (images) corresponding to the current state (i.e., camera angle). The state of each object is maintained throughout the entire process. The initial state (camera angle) of each object corresponds to the image in the problem statement.

The goal of the task is to verify whether an object can be rotated to obtain the same view as one of the alternatives. For the problems in question, this is equivalent to rotating the alternatives to obtain the view of the original.

The imagery module allows rotating only the alternatives. The imagery module helps solve the problem by actually rotating the objects and obtaining a snapshot of the current state, reducing this way, the validation step to a more simple image comparison.

Working with the imagery module is an iterative process, controlled externally. On your turn, perform the necessary analysis based on the provided images, and at the end generate a set of rotations to perform. The imagery module will then apply these rotations and return a new image corresponding to the new state of the object.

Do not describe or simulate the imagery module's behavior or the resulting images. The process is handled externally.  

Rotations are performed in camera space (relative to the current view), simulating the inverse of camera movement. Intuitively, this matches the view of manipulating an object in your hands: the object spins around its center while the camera (your viewpoint) remains fixed.

The possible rotation commands are:
- `left:value` (object is rotated to left)
- `right:value` (object is rotated to right)
- `up:value` (object is rotated up)
- `down:value` (object is rotated down)
- `rotate:cw:value` (object rotates clockwise in the image plane)
- `rotate:ccw:value` (object rotates counterclockwise in the image plane)

`value` refers to the rotation angle in degrees. Angle 0 is also valid and generates a snapshot of the current state.

Example sequence of commands: `right:0,right:30,up:20`
In this example, initially a rotation of value 0 is performed, meaning the object does not move, consequently a snapshot of the current state is generated. Then, a rotation to the right is applied (equivalent to the camera rotating to the left), and a snapshot is generated again. Finally, a rotation up is performed, and a snapshot is generated again. The result is a grid image containing these 3 post-rotation images.

# OUTPUT

Return your response in JSON format, following the format below:

```json
{
  "memory": {
    "rationale": "your justification up to this point",
    "partial_conclusion": {
      "A": "unknown"|"probably_not_the_answer"|"probably_the_odd_one",
      "B": "unknown"|"probably_not_the_answer"|"probably_the_odd_one",
      "C": "unknown"|"probably_not_the_answer"|"probably_the_odd_one"
    }
  },
  "iteration_number": 1,
  "commands": [
    {
      "target": "A"|"B"|"C",
      "rotation_sequence": "right:15,right:15,up:10"
    }
  ],
  "final_answer": null
}
```

Details of the output fields:
- `memory`: Your `memory` of reasoning. The entire memory history is provided in the iteration context.
- `commands`: Sequence of rotations, for one or more target objects.
- `final_answer`: Final response, if you have the definitive answer. Otherwise, leave as null.
- `iteration_number`: Iteration counter. Start with 1 and increment this number each turn.

Enclose the JSON object in ```json and ```.

*IMPORTANT*
In you turn, just generate exactly one JSON output and finish. DON'T simulate the iteration or the imagery module behaviour. It is handled externally.


# CONVERSATION CONTEXT

In the conversation context you will find:
- the text and image from the problem statement.
- all the previous iteration output you have generated.
- the images generated by the imagery module, from the last iteration only.
- the `original` object snapshot to help comparision.

# STRATEGY
- Perform at least 5 iterations before giving the final answer.

"""

# ... The camera does an orbital movement.

prompt_p20260306_03 = """
# TASK AND ITERATIVE PROCESS

Your task is to solve a 3D model rotation problem.

The problem includes an image with 4 figures, and the following statement:
`The left image shows the original cube stack made of equal-sized small cubes. Which of the options on the right cannot be obtained by rotating the original cube stack? Please answer from options A, B or C.`

# IMAGE MODULE

To solve this problem, you will work together with a tool called the imagery module.

The imagery module holds a 3D representation of the problem objects and perform rotation operations on your behalf, and generate snapshots (images) corresponding to the current state (i.e., camera angle). The state of each object is maintained throughout the entire process. The initial state (camera angle) of each object corresponds to the image in the problem statement.

The problem asks whether one object can have the same view as the other through rotation. The imagery module helps solve the problem by actually performing the rotation and providing the view after-rotation, enabling a try-rotate and check loop process, you don't need to "imagine" it. You can request a direct rotation to a desired final target state or do it incrementally, in a loop rotate-verify until get the disired view of conclude that is not possible. It is like take the objects in you hands, and play if around checking visually if you have a match.

The problem asks to rotate the original to match the alternative, but for the problems presented here, it is equivalent rotate the alternative to match the original. The imagery module allows rotate only the alternatives.

Working with the imagery module is an iterative process, controlled externally. It work in TURNS between your and the imagery module. On your turn, do the analysis based on the provided images, and generate rotation instructions to the imagery module. Then, the imagery module, on its turn, will apply these rotations and return the snapshot images of the objects in the new state. Then it is your turn, and so on.

Rotations commands are defined in camera space (relative to the current view), simulating the inverse of camera movement. Intuitively, this matches the view of manipulating an object in your hands: the object spins around its center while the camera (your viewpoint) remains fixed. 

Possible commands are:
- `left:value` (object is rotated to left)
- `right:value` (object is rotated to right)
- `up:value` (object is rotated up)
- `down:value` (object is rotated down)
- `rotate:cw:value` (object rotates clockwise in the image plane)
- `rotate:ccw:value` (object rotates counterclockwise in the image plane)

`value` refers to the rotation angle in degrees. Angle 0 is also valid and can be used to get a snapshot of the current state.

# OUTPUT

Return your response in JSON format, following the format below:

```json
{
  "memory": {
    "rationale": "your justification up to this point",
    "partial_conclusion": {
      "A": "unknown"|"probably_not_the_answer"|"probably_the_odd_one",
      "B": "unknown"|"probably_not_the_answer"|"probably_the_odd_one",
      "C": "unknown"|"probably_not_the_answer"|"probably_the_odd_one"
    }
  },
  "iteration_number": 1,
  "commands": [
    {
      "target": "A"|"B"|"C",
      "rotation_sequence": "right:15,right:15,up:10"
    }
  ],
  "final_answer": null
}
```

Details of the output fields:
- `memory`: Generate your rationale and partial conclusion to help trace your reasoning process. This block will be provided as context in future turns during the iteration, so it will serve as your memory throughout the iterative process.
- `commands`: Rotation instructions for the imagery module. You can generate for one or more targets. Rotation sequence can have one or more commands, separated by comma. Each command generates a snapshot image of after rotation view, and will be combined in a grid image, per target, having the effect of a sequence showing the object rotating incrementally. 
- `final_answer`: The answer for the problem, if you have a conclusion. Otherwise, leave as null.
- `iteration_number`: Iteration counter. Start with 1 and increment this number each turn.

Enclose the JSON object in ```json and ```.

*IMPORTANT*
In you turn, generate exactly one JSON output and FINISH. DON'T simulate the iteration or the imagery module turn. It is handled externally.


# CONVERSATION CONTEXT

The conversation context, in each turn, will contain the following content:
- The text and image from the problem statement.
- All the previous output you have generated.
- The images generated by the imagery module, from the last iteration only.
- The `original` object snapshot to help comparision.

# STRATEGY
- Perform at least 5 iterations before giving the final answer.

"""

prompt_p20260306_03_ablation_360view = """
# TASK AND ITERATIVE PROCESS

Your task is to solve a 3D model rotation problem.

The problem includes an image with 4 figures, and the following statement:
`The left image shows the original cube stack made of equal-sized small cubes. Which of the options on the right cannot be obtained by rotating the original cube stack? Please answer from options A, B or C.`

# IMAGE MODULE

To solve this problem, you will work together with a tool called the imagery module.

The imagery module holds a 3D representation of the problem objects and perform rotation operations on your behalf, and generate snapshots (images) corresponding to the current state (i.e., camera angle). The state of each object is maintained throughout the entire process. The initial state (camera angle) of each object corresponds to the image in the problem statement.

The problem asks whether one object can have the same view as the other through rotation. The imagery module helps solve the problem by actually performing the rotation and providing the view after-rotation, enabling a try-rotate and check loop process, you don't need to "imagine" it. You can request a direct rotation to a desired final target state or do it incrementally, in a loop rotate-verify until get the disired view of conclude that is not possible. It is like take the objects in you hands, and play if around checking visually if you have a match.

The problem asks to rotate the original to match the alternative, but for the problems presented here, it is equivalent rotate the alternative to match the original. The imagery module allows rotate only the alternatives.

Working with the imagery module is an iterative process, controlled externally. It work in TURNS between your and the imagery module. On your turn, do the analysis based on the provided images, and generate rotation instructions to the imagery module. Then, the imagery module, on its turn, will apply these rotations and return the snapshot images of the objects in the new state. Then it is your turn, and so on.

Rotations commands are defined in camera space (relative to the current view), simulating the inverse of camera movement. Intuitively, this matches the view of manipulating an object in your hands: the object spins around its center while the camera (your viewpoint) remains fixed. 

Possible commands are:
- `left:value` (object is rotated to left)
- `right:value` (object is rotated to right)
- `up:value` (object is rotated up)
- `down:value` (object is rotated down)
- `rotate:cw:value` (object rotates clockwise in the image plane)
- `rotate:ccw:value` (object rotates counterclockwise in the image plane)

`value` refers to the rotation angle in degrees. Angle 0 is also valid and can be used to get a snapshot of the current state.

# OUTPUT

Return your response in JSON format, following the format below:

```json
{
  "memory": {
    "rationale": "your justification up to this point",
    "partial_conclusion": {
      "A": "unknown"|"probably_not_the_answer"|"probably_the_odd_one",
      "B": "unknown"|"probably_not_the_answer"|"probably_the_odd_one",
      "C": "unknown"|"probably_not_the_answer"|"probably_the_odd_one"
    }
  },
  "iteration_number": 1,
  "commands": [
    {
      "target": "A"|"B"|"C",
      "rotation_sequence": "right:15,right:15,up:10"
    }
  ],
  "final_answer": null
}
```

Details of the output fields:
- `memory`: Generate your rationale and partial conclusion to help trace your reasoning process. This block will be provided as context in future turns during the iteration, so it will serve as your memory throughout the iterative process.
- `commands`: Rotation instructions for the imagery module. You can generate for one or more targets. Rotation sequence can have one or more commands, separated by comma. Each command generates a snapshot image of after rotation view, and will be combined in a grid image, per target, having the effect of a sequence showing the object rotating incrementally. 
- `final_answer`: The answer for the problem, if you have a conclusion. Otherwise, leave as null.
- `iteration_number`: Iteration counter. Start with 1 and increment this number each turn.

Enclose the JSON object in ```json and ```.

*IMPORTANT*
In you turn, generate exactly one JSON output and FINISH. DON'T simulate the iteration or the imagery module turn. It is handled externally.


# CONVERSATION CONTEXT

The conversation context, in each turn, will contain the following content:
- The text and image from the problem statement.
- All the previous output you have generated.
- The images generated by the imagery module, from the last iteration only.
- The `original` object snapshot to help comparision.

# STRATEGY
- Perform at least 5 iterations before giving the final answer.

# HINTS
Generating a larger sequence that provides a 360-degree visualization can help quickly understand the object's structure, in addition to generating views for faster comparison. If one of the snapshots is similar to the original, then it can be concluded that it is achievable, and there is no need for incremental rotation.

Examples of generation sequences are (but not limited to):
- "left:90,left:90,up:90,down:180,up:90,left:180"
- "left:90,left:90,left:90,up:90,down:180,up:90"
- "left:0,up:50,left:45, left:45,left:45,left:45,left:45,left:45,left:45,left:45,down:140,left:45,left:45,left:45,left:45,left:45,left:45,left:45,left:45"
- "left:0,left:45,left:45,left:45,left:45,left:45,left:45,left:45,left:45,up:45,left:45,left:45,left:45,left:45,down:90,left:45,left:45,left:45,left:45,left:45,left:45"

"""


prompt = prompt_p20260306_03_ablation_360view

reasoner_for_final_answer = """
For this visual problem, generate the answer in the following json format:
```json
{
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


def rationale_with_imagery_response_org(rationales, imagery_images):
    # ensure that rationale and imagery response are in the same length
    assert len(rationales) == len(
        imagery_images
    ), "Rationale and imagery response must be in the same length"

    rationale_with_imagery_resonse = []
    for i in range(len(rationales)):
        rationale_with_imagery_resonse.append(rationales[i])
        # for image, include only the last 1 images
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


def rationale_with_imagery_response(rationales, imagery_images):
    # ensure that rationale and imagery response are in the same length
    assert len(rationales) == len(
        imagery_images
    ), "Rationale and imagery response must be in the same length"

    if len(rationales) <= 0:
        return []
    rationale_with_imagery_response = []
    rationale_with_imagery_response.append(
        dict(
            role="assistant",
            content="# PAST ITERATION CONTEXT\n"
            + "\n---\n".join(r["content"] for r in rationales),
        )
    )
    # add the last iteration image
    rationale_with_imagery_response.append(
        dict(role="user", content="# LAST ITERATION RESULT SNAPSHOTS\n")
    )
    for image_url, content in imagery_images[-1]:
        rationale_with_imagery_response.append(
            dict(
                # role="assistant",
                role="user",  # gpt 5.2 not support assistant role for image content
                image_url=image_url,
            )
        )

    return rationale_with_imagery_response


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


class ToolsBackedImageryReasoner_Eval_08101_Prompt3_Freeze1_Ablation1:

    REASONING_MODEL = "gpt-5.2-2025-12-11"
    # REASONING_MODEL = "gpt-5.4-2026-03-05"

    @classmethod
    async def reason_loop(
        cls,
        chat_message: ChatMessage,
        model: str | ModelWithParameters,
        options=None,  # not used by the caller
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
                reasoner_system_message = prompt
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
                            "temperature": 0.0,
                            # "response_json_schema": response_schema,
                        },
                    )

                    response_dict = parser_json(response)
                    if not isinstance(response_dict, dict):
                        print(f"Not a dictionary. RETRY {reasoning_retry_cout}")
                        continue

                    final_answer = response_dict.get("final_answer")
                    commands = response_dict.get("commands")
                    if final_answer:
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
                commands_map = {  # always include the original current state
                    "original": ["left:0"],
                }
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
