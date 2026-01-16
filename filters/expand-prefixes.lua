local prefixes = {
  wd      = "http://www.wikidata.org/entity/",
  wdt     = "http://www.wikidata.org/prop/direct/",
  wdtn    = "http://www.wikidata.org/prop/direct-normalized/",
  wdno    = "http://www.wikidata.org/prop/novalue/",
  wds     = "http://www.wikidata.org/entity/statement/",
  p       = "http://www.wikidata.org/prop/",
  ps      = "http://www.wikidata.org/prop/statement/",
  pq      = "http://www.wikidata.org/prop/qualifier/",
  schema  = "http://schema.org/",
  rdfs    = "http://www.w3.org/2000/01/rdf-schema#",
  rdf     = "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
  dcterms = "http://purl.org/dc/terms/",
  dc      = "http://purl.org/dc/elements/1.1/",
  foaf    = "http://xmlns.com/foaf/0.1/",
  skos    = "http://www.w3.org/2004/02/skos/core#",
  owl     = "http://www.w3.org/2002/07/owl#",
  bibo    = "http://purl.org/ontology/bibo/",
  dbo     = "http://dbpedia.org/ontology/",
  dbr     = "http://dbpedia.org/resource/",
  cc      = "http://creativecommons.org/ns#",
  orcid   = "https://orcid.org/",
  viaf    = "http://viaf.org/viaf/"
}

local function expand(value)
  if type(value) ~= "string" then
    return value
  end
  local p, rest = value:match("^(%w+):(.*)$")
  if p and prefixes[p] then
    return prefixes[p] .. rest
  end
  return value
end

function Span(el)
  for k, v in pairs(el.attributes) do
    el.attributes[k] = expand(v)
  end
  return el
end
