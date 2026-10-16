---
name: boy-scout
description: Use when fixing, editing, changing, debugging, or working with code in ANY language — Python, TypeScript/JavaScript, Ruby, Go, Java, Rust, SQL, shell, config. Applies the Boy Scout Rule—always leave code cleaner than you found it. Routes to a language-specific clean code skill when one exists, and applies the catalog directly when none does.
---

# The Boy Scout Rule

> "Always leave the campground cleaner than you found it."
> — Robert Baden-Powell

> "Always check a module in cleaner than when you checked it out."
> — Robert C. Martin, *Clean Code*

## The Philosophy

You don't have to make every module perfect. You simply have to make it **a little bit better** than when you found it.

If we all followed this simple rule:
- Our systems would gradually get better as they evolved
- Teams would care for the system as a whole
- The relentless deterioration of software would end

## The rule is language-independent; the tooling is not

The catalog this rule draws on — naming, function size, comments that say *why*, DRY, boundary conditions — describes how people read code, not how a compiler parses it. It applies to a Rust trait, a Bash function, a Terraform module and a SQL view.

What is *not* portable is the tooling. The `clean-*` skills below are written against Python, and `rails-clean-code` against Ruby on Rails. Outside those, there is no specialized skill to load: apply the catalog directly. Do not invoke a Python skill to review TypeScript — its examples and rule numbers will be about a language that isn't on screen.

**Cleaner means cleaner *in the idiom of the file you are editing.*** A comprehension is the clean form in Python and doesn't exist in Go; a guard clause reads well everywhere; explicit types are a fix in TypeScript and noise in a dynamically typed script with no type checker. Match the surrounding code's conventions — including its language for identifiers and comments — before importing a habit from somewhere else.

## When Working on Code

Every time you touch code, look for **at least one small improvement**:

### Quick Wins (Do These Immediately)
- Rename a poorly named variable, function or type
- Delete a redundant comment — one that restates the code instead of explaining why
- Remove dead code, unreachable branches, unused imports
- Replace a magic number or magic string with a named constant
- Extract a deeply nested block into a well-named function

### Deeper Improvements (When Time Allows)
- Split a function that does multiple things
- Remove duplication (DRY)
- Add missing boundary checks — empty, zero, negative, null, the maximum
- Improve test coverage where the change you just made is untested

## The Rule in Practice

The syntax below is incidental — the shape of the change is the point.

```
# Asked to fix a bug in this function:
proc(d, x, flag):
    for i in d:
        if i > 0:
            if flag: x.append(i * 1.0825)   # tax
            else:    x.append(i)
    return x
```

Don't just fix the bug and leave. Leave it cleaner:

```
TAX_RATE = 0.0825

positiveValuesWithTax(values, applyTax):
    rate = applyTax ? 1 + TAX_RATE : 1
    return [v * rate for v in values if v > 0]
```

**What changed, and why each one travels across languages:**
- ✅ The name says what it returns, not that it "processes" (N1)
- ✅ Parameters are named after what they hold (N1)
- ✅ `1.0825` became a named constant — the number no longer needs a comment (G25)
- ✅ The caller's list is no longer mutated as a side channel; the result is returned (F2)
- ✅ The nesting collapsed once the condition became an expression (G34)
- ✅ Types written where the language has them, omitted where it doesn't

## Skill Orchestration

Route by the language on screen. Load the specialized skill **only** when it matches:

| Language of the code | What to load |
|---|---|
| Python | `python-clean-code` (master), plus `clean-names`, `clean-comments`, `clean-functions`, `clean-general`, `clean-tests` by task |
| Ruby / Ruby on Rails | `rails-clean-code` |
| Anything else — TypeScript, JavaScript, Go, Java, Rust, C#, PHP, SQL, shell, config | No specialized skill exists. Apply the catalog above directly, in that language's idiom. |

If the change spans several languages, route per file, not per task.

## The Mindset

**Don't:**
- Leave code worse than you found it
- Say "that's not my code"
- Wait for a dedicated refactoring sprint
- Make massive changes unrelated to your task
- Reformat or restyle a file that has no formatter configured — that buries your change in noise

**Do:**
- Make one small improvement with every commit
- Fix what you see, even if you didn't break it
- Keep changes proportional to your task
- Leave a trail of quality improvements

## AI Behavior

When working on code:
1. Complete the requested task first
2. Identify at least one small cleanup opportunity
3. Apply the language-specific skill if one exists; otherwise apply the catalog directly
4. Note the improvement made (e.g., "Also cleaned up: renamed `x` to `results` for clarity")

When reviewing code:
1. Load the skill that matches the language; if none matches, review against the catalog
2. Flag violations by rule number where the catalog gives one
3. Suggest incremental improvements, not complete rewrites

## The Boy Scout Promise

Every piece of code you touch gets a little better. Not perfect—just better.

Over time, better compounds into excellent.
