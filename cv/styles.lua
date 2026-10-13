-- Pandoc filter for the CV's LaTeX renderer.
--
-- cv.qmd renders through a custom template (cv/template.tex) whose section
-- macro is \cvsection (a centred boxed title), not LaTeX \section. Left as-is,
-- that means the PDF has no bookmark/outline tree and every heading — section
-- or entry — lands at the same outline level.
--
-- This filter keeps the \cvsection visual for every heading but, based on the
-- Markdown heading level, emits a matching \pdfbookmark:
--   ## Section  -> bookmark level 0 (top-level)
--   ### Entry   -> bookmark level 1 (nested under the most recent section)
-- A counter gives each bookmark a unique destination, satisfying hyperref/
-- bookmark's requirement that the dest name be distinct.

local section_count = 0
local entry_count = 0

function Header(el)
  local text = pandoc.utils.stringify(el.content)
  local latex = '\\cvsection{' .. text .. '}'
  if el.level <= 2 then
    section_count = section_count + 1
    latex = latex .. '\\pdfbookmark[0]{' .. text .. '}{cvsection' .. section_count .. '}'
  else
    entry_count = entry_count + 1
    latex = latex .. '\\pdfbookmark[1]{' .. text .. '}{cventry' .. entry_count .. '}'
  end
  return pandoc.RawInline('latex', latex)
end
