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

local function latex_text(text)
  return (text:gsub("[\\{}#$%%&_~^]", function(char)
    return latex_escapes[char]
  end))
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
