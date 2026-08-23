# How the Pieces Fit Together (Simple Explanation)

You've now got a lot of names floating around — `Context`, `Registry`,
`Backend`, `Client`, `PromptBuilder`, `Logger`, `Agent`, the "Run DSL", the
"REPL". This doc is just: what is each one, and how do they connect. No new
code, just the map.

## 1. The one-sentence version

- **The small objects** (`Context`, `Registry`, `Backend`, `Client`,
  `PromptBuilder`, `Logger`) each do one boring, narrow job.
- **`Agent`** is the thing that actually *uses* all of them to have one
  back-and-forth exchange with the model (including calling tools if the
  model asks for them) until it produces a final answer.
- **The "Run DSL"** is not a separate engine — it's just the tiny
  `tool "name" do |...| ... end` syntax you write inside a block. It's how
  *you* tell the registry which tools exist.
- **`Boukensha.run`** and **`Boukensha.repl`** are two "starter" methods that
  build all the small objects for you (so you don't have to), run your Run
  DSL block to register tools, and then either run one `Agent` once (`.run`)
  or keep making new `Agent`s in a loop until you say stop (`.repl`).

That's the whole confusion, usually: **the DSL and the REPL are not
alternatives to the Agent — they're two different ways of *starting* it.**

## 2. The small objects — what each one actually is

Think of these as departments in a small office, each with one job:

| Object | Its one job | Plain description |
|---|---|---|
| `Context` | remembers things | Holds the conversation so far (`messages`), the tools available (`tools`), and the system prompt. This is the "memory." |
| `Tool` | describes one capability | Just a name + description + the actual Ruby code to run (a `Struct`, no logic). |
| `Message` | one line of the transcript | Who said it (`role`), what was said (`content`). |
| `Registry` | the tool phonebook | Lets you *register* a tool (`registry.tool("read_file") { ... }`) and *dispatch* one by name when the model asks for it. Writes into `Context`'s `tools`, doesn't keep its own copy. |
| `Backend` (Anthropic/OpenAI/Gemini/Ollama/OllamaCloud) | speaks one provider's language | Translates `Context`'s messages/tools into that provider's specific JSON shape, and translates that provider's response back into one shape every backend agrees on. |
| `PromptBuilder` | a thin messenger | Just forwards calls to whichever `Backend` it was given. Exists so `Client`/`Agent` don't need to know which provider is in use. |
| `Client` | makes the actual phone call | Sends the HTTP request to the provider, retries on network hiccups or rate limits, decodes the JSON response. Knows nothing about messages or tools — just bytes over HTTP. |
| `Logger` | the black-box recorder | Writes every step (prompt sent, tool called, response received) to a `.jsonl` file on disk. Doesn't print anything to your screen — file only. |
| `Config` | reads the settings | Loads `.env` (secrets) and `settings.yaml` (provider, model, limits) once, at startup. |

None of these know about "having a conversation" — that's the next layer up.

## 3. `Agent` — the thing that actually runs one turn

`Agent#run` is a loop with exactly one question at each step: *did the model
ask to use a tool, or did it give a final answer?*

```
Agent#run:
  loop:
    ask Client for a response (via PromptBuilder/Backend)
    if the model wants to call a tool:
      run it (via Registry), record the result, ask again
    else:
      that's the final answer — stop and return it
```

`Agent` is the only object that holds references to *all* the small ones —
`Context`, `Registry`, `PromptBuilder`, `Client`, `Logger` — and drives them
in sequence. Everything below it (`Client`, `Backend`, …) is one-directional
plumbing; `Agent` is where the actual decision-making loop lives.

**One `Agent` = one turn.** It's built, it runs once, and it's done. It
doesn't loop across multiple user questions — that's not its job.

## 4. The "Run DSL" — not a second engine, just a tiny vocabulary

This is the part that trips people up. "DSL" (domain-specific language)
sounds like a big separate system. It's actually just **one method**:

```ruby
# RunDSL — this is the entire "language"
def tool(name, description:, parameters: {}, &block)
  @registry.tool(name, description: description, parameters: parameters, &block)
end
```

When you write:

```ruby
Boukensha.run(task: "...") do
  tool "read_file", description: "...", parameters: { ... } do |path:|
    File.read(path)
  end
end
```

...the block runs with `self` set to a `RunDSL` object, so calling `tool`
inside it is really just calling `RunDSL#tool`, which is really just calling
`Registry#tool`, which stores the tool on the shared `Context`. That's it —
"the DSL" is the vocabulary (`tool`) you use to talk to the `Registry`
*before* the `Agent` starts running. It has no loop, no state, no
intelligence of its own.

## 5. `Boukensha.run` and `Boukensha.repl` — the two starters

Both of these methods do the exact same setup work:

1. Load `Config` (`.env` + `settings.yaml`).
2. Figure out the system prompt, model, provider, and API key.
3. Build `Context`, `Registry`, the right `Backend`, `PromptBuilder`,
   `Client`, `Logger`.
4. Run your Run DSL block, so your `tool` calls register on the `Registry`.

Where they differ is what happens *after* that setup:

```
Boukensha.run(task: "...")  { tool ... }
  → builds ONE Agent, adds your task as a message, calls agent.run ONCE
  → returns the final text
  → done — Context is thrown away

Boukensha.repl { tool ... }
  → hands everything to a Repl object, which loops:
      print "boukensha> ", read one line from the terminal
      if it's a command (/exit, /clear, ...) → handle it directly
      else → build a NEW Agent (same shared Context/Registry/Client/Logger)
             and call agent.run for THIS turn only
      → print the answer, go back to the prompt
  → keeps going until /exit, /quit, or Ctrl-D
```

So the REPL isn't a different kind of Agent — it's a `while` loop around
"make an `Agent`, run it once, print the result," reusing the *same*
`Context` every time. That reuse is the entire trick behind conversation
memory: since `Context#messages` never gets rebuilt between turns, turn 3's
`Agent` sees turns 1 and 2 sitting right there in `Context`, exactly as if
one long conversation had been happening the whole time — even though, under
the hood, a fresh disposable `Agent` object was built for each turn.

## 6. The full picture, top to bottom

```
you write:  Boukensha.repl(model: "...") { tool "read_file" { ... } }
                      │
                      ▼
        Boukensha.repl (a starter method)
          ├─ Config             → reads .env / settings.yaml
          ├─ Context, Registry  → built fresh, empty
          ├─ RunDSL#tool  ──────▶ registers your tools onto Context
          ├─ Backend, PromptBuilder, Client, Logger  → built once
          └─ Repl.new(...).start
                      │
                      ▼
              Repl#start  (the REPL loop — lives in the terminal)
                loop:
                  read one line from you
                  /clear, /exit, etc.?  → handle here, no Agent involved
                  otherwise:
                        │
                        ▼
                  Agent.new(same Context/Registry/Client/Logger).run
                    loop:
                      Client → Backend → provider API
                      tool_use?  → Registry#dispatch → run your tool block
                      final text? → save to Context, return it
                        │
                        ▼
                  Repl prints the answer, loops back to the prompt
```

**Retain this one idea above everything else:** `Context` is the only thing
that actually accumulates across turns. `Agent`s are cheap and disposable —
a new one every turn — but they all point at the same `Context`, and that
shared pointer is the entire mechanism behind "the REPL remembers what you
said three questions ago."
