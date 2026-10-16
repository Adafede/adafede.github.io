-- Pandoc filter for the CV's LaTeX renderer. It distinguishes section headings
-- from dated entries and emits a matching PDF bookmark for each:
--   ## Section  -> bookmark level 0 (top-level)
--   ### Entry   -> bookmark level 1 (nested under the most recent section)
-- A counter gives each bookmark a unique destination, satisfying hyperref/
-- bookmark's requirement that the dest name be distinct.

local pandoc = require 'pandoc'
local section_count = 0
local entry_count = 0
local latex_escapes = {
  ["\\"] = "\\textbackslash{}",
  ["{"] = "\\{",
  ["}"] = "\\}",
  ["#"] = "\\#",
  ["$"] = "\\$",
  ["%"] = "\\%",
  ["&"] = "\\&",
  ["_"] = "\\_",
  ["~"] = "\\textasciitilde{}",
  ["^"] = "\\textasciicircum{}",
}

-- Pandoc's smart extension runs on the Markdown before this filter sees it, so
-- `2011 -- 2016` has already become `2011 – 2016` with a real U+2013 by the
-- time we get here. Handing that straight to LaTeX silently loses it: the
-- document is lualatex with T1 + Latin Modern and no `ltunicode`, and that
-- encoding has no slot for U+2013. LaTeX reports "Missing character" and drops
-- it, which is why the date ranges printed as "2022 present" and every curly
-- quote in a heading vanished. The middle dot was worse than missing -- it
-- picked up a glyph from the neighbouring slot and printed as "u-circumflex".
--
-- So: translate the smart punctuation back into LaTeX's own spelling before
-- escaping. `--` is an en dash and `---` an em dash in LaTeX source, so this
-- is the exact inverse of what Pandoc did.
-- Keyed by codepoint, because that is what `replace_unicode` decodes.
local unicode_to_latex = {
  [0x00A0] = "~",                    -- no-break space
  [0x00A9] = "\\textcopyright{}",
  [0x00AE] = "\\textregistered{}",
  [0x00B1] = "\\textpm{}",           -- plus-minus
  [0x00B7] = "\\textperiodcentered{}",-- middle dot
  [0x00B0] = "\\textdegree{}",        -- degree sign
  [0x00D7] = "\\texttimes{}",        -- multiplication sign
  [0x2010] = "-",                    -- hyphen
  [0x2011] = "-",                    -- non-breaking hyphen
  [0x2012] = "--",                   -- figure dash
  [0x2013] = "--",                   -- en dash
  [0x2014] = "---",                  -- em dash
  [0x2015] = "---",                  -- horizontal bar
  [0x2018] = "`",                    -- left single quote
  [0x2019] = "'",                    -- right single quote / apostrophe
  [0x201A] = "'",                    -- single low quote
  [0x201C] = "``",                   -- left double quote
  [0x201D] = "''",                   -- right double quote
  [0x201E] = "``",                   -- double low quote
  [0x2022] = "\\textbullet{}",       -- bullet
  [0x2026] = "\\ldots{}",            -- ellipsis
  [0x2192] = "$\\rightarrow$",
}

-- Decode one UTF-8 sequence at `i`, returning the codepoint and the index just
-- past it. Lua patterns match per byte, so `gsub("[^\128-\255]")` would hand
-- back the three bytes of an en dash separately rather than the character.
local function utf8_codepoint(s, i)
  local c = s:byte(i)
  if not c or c < 0x80 then
    return c, i + 1
  end
  local extra, codepoint
  if c >= 0xF0 then
    extra, codepoint = 3, c - 0xF0
  elseif c >= 0xE0 then
    extra, codepoint = 2, c - 0xE0
  elseif c >= 0xC0 then
    extra, codepoint = 1, c - 0xC0
  else
    -- A stray continuation byte: pass it through unchanged.
    return c, i + 1
  end
  for _ = 1, extra do
    i = i + 1
    local cc = s:byte(i)
    if not cc then
      return nil, i
    end
    codepoint = codepoint * 64 + (cc - 0x80)
  end
  return codepoint, i + 1
end

local function replace_unicode(s)
  local out = {}
  local i = 1
  while i <= #s do
    local codepoint, next_i = utf8_codepoint(s, i)
    -- The whole sequence, not just its first byte: a codepoint with no LaTeX
    -- spelling here is still a character the document has to typeset, and
    -- emitting the lead byte alone leaves invalid UTF-8 in the output.
    out[#out + 1] = (codepoint and unicode_to_latex[codepoint])
      or s:sub(i, next_i - 1)
    i = next_i
  end
  return table.concat(out)
end

local function latex_text(text)
  local escaped = (text:gsub("[\\{}#$%%&_~^]", function(char)
    return latex_escapes[char]
  end))
  -- Runs after the escape pass on purpose: the replacements above contain
  -- braces of their own, which the escape pass would otherwise turn into
  -- "\{". Escaping only touches ASCII specials, so doing it first cannot
  -- disturb the multi-byte characters this one reads.
  return replace_unicode(escaped)
end

function Header(el)
  local text = pandoc.utils.stringify(el.content)
  local escaped = latex_text(text)
  local latex
  if el.level <= 2 then
    latex = '\\cvsection{' .. escaped .. '}'
    section_count = section_count + 1
    latex = latex .. '\\pdfbookmark[0]{' .. escaped .. '}{cvsection' .. section_count .. '}'
  else
    local title, date = text:match("^(.-)%s*%((%d%d%d%d[^()]*)%)$")
    title = latex_text(title or text)
    date = latex_text(date or "")
    latex = '\\cventry{' .. title .. '}{' .. date .. '}'
    entry_count = entry_count + 1
    latex = latex .. '\\pdfbookmark[1]{' .. escaped .. '}{cventry' .. entry_count .. '}'
  end
  return pandoc.RawInline('latex', latex)
end

-- Deliberately no `Str` handler here, though body text has the same font
-- problem: Pandoc's LaTeX writer leaves `·`, `±`, `×`, `©` and `→` as raw UTF-8
-- and T1 has no slot for them. A `Str` handler that rewrote those does conflict
-- with the `Header` handler above -- Pandoc feeds the heading's inline content
-- through it first, and the date range loses its dashes -- so the fix, if it is
-- ever needed, is a separate filter applied to body text rather than an extra
-- function in this one. Nothing in the CV sources currently uses those
-- characters; `rg '[·±×©→]' cv/` is empty.
