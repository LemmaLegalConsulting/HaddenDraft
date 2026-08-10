import React, { useEffect, useMemo, useState } from "react";
import { BookOpen, ChevronDown, ChevronRight, FileText, Landmark, Library, Loader2, Search, X } from "lucide-react";

import { api } from "../api/client.js";
import {
  DEFAULT_PAGE_SIZE,
  SORT_OPTIONS,
  activeFilters,
  catalogParams,
  filterCount,
  hasMore,
  orderedFacets,
  pageSummary,
  removeFacetValue,
  toggleFacetValue,
} from "./caseCatalog.js";
import {
  countSections,
  documentSubtitle,
  expandedForFilter,
  sectionCitation,
  shelves,
  toggleNode,
} from "./libraryBrowse.js";
import { SourceFullViewButton } from "./MarkdownResponse.jsx";

const TABS = [
  { id: "cases", label: "Cases", icon: Landmark },
  { id: "treatise", label: "Treatises and handbooks", icon: BookOpen },
  { id: "statute", label: "Statutes", icon: Library },
];

function CaseCatalog({ onOpenSource }) {
  const [draftQuery, setDraftQuery] = useState("");
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState({});
  const [sort, setSort] = useState("newest");
  const [results, setResults] = useState([]);
  const [payload, setPayload] = useState(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  async function load({ nextQuery = query, nextFilters = filters, nextSort = sort, offset = 0 } = {}) {
    setBusy(true);
    setError("");
    try {
      const response = await api.caselawCatalog(
        catalogParams({ query: nextQuery, filters: nextFilters, sort: nextSort, offset }),
      );
      setPayload(response);
      setResults((current) => (offset ? [...current, ...(response.results || [])] : response.results || []));
    } catch (err) {
      setError(err.message || "Could not load the case catalog.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function narrow(facet, value) {
    const nextFilters = toggleFacetValue(filters, facet, value);
    setFilters(nextFilters);
    load({ nextFilters });
  }

  function drop(facet, value) {
    const nextFilters = removeFacetValue(filters, facet, value);
    setFilters(nextFilters);
    load({ nextFilters });
  }

  function clearAll() {
    setFilters({});
    setQuery("");
    setDraftQuery("");
    load({ nextQuery: "", nextFilters: {} });
  }

  const facetLabels = payload?.facetLabels || {};
  const facetGroups = orderedFacets(payload?.facets, facetLabels);
  const chips = activeFilters(filters, facetLabels);
  const summary = pageSummary({
    total: payload?.total || 0,
    offset: 0,
    shown: results.length,
    corpusTotal: payload?.corpusTotal || 0,
  });

  return (
    <div className="case-catalog">
      <form
        className="case-catalog-search"
        onSubmit={(event) => {
          event.preventDefault();
          setQuery(draftQuery);
          load({ nextQuery: draftQuery });
        }}
      >
        <input
          aria-label="Search the case catalog"
          placeholder="Search case names, dockets, facts, and citations"
          value={draftQuery}
          onChange={(event) => setDraftQuery(event.target.value)}
        />
        <button className="secondary" type="submit" disabled={busy}>
          {busy ? <Loader2 className="spin" size={14} /> : <Search size={14} />}
        </button>
        <label className="case-catalog-sort">
          <span>Sort</span>
          <select
            value={sort}
            onChange={(event) => {
              setSort(event.target.value);
              load({ nextSort: event.target.value });
            }}
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
      </form>
      {(chips.length > 0 || query) && (
        <div className="case-catalog-chips" aria-label="Active narrowing">
          {query && (
            <button type="button" className="case-catalog-chip" onClick={() => { setQuery(""); setDraftQuery(""); load({ nextQuery: "" }); }}>
              Search: {query} <X size={12} />
            </button>
          )}
          {chips.map((chip) => (
            <button
              key={`${chip.facet}-${chip.value}`}
              type="button"
              className="case-catalog-chip"
              onClick={() => drop(chip.facet, chip.value)}
            >
              {chip.label}: {chip.value} <X size={12} />
            </button>
          ))}
          {filterCount(filters) > 0 && (
            <button type="button" className="text-link-button" onClick={clearAll}>Clear all</button>
          )}
        </div>
      )}
      {error && <div className="inline-error">{error}</div>}
      <div className="case-catalog-layout">
        <aside className="case-catalog-facets" aria-label="Narrow by metadata">
          {facetGroups.map((group) => (
            <details key={group.facet} open={group.items.some((item) => item.selected) || group.items.length <= 12}>
              <summary>{group.label} <small>{group.items.length}</small></summary>
              <div className="case-catalog-facet-values">
                {group.items.map((item) => (
                  <button
                    key={`${group.facet}-${item.value}`}
                    type="button"
                    className={`case-facet-chip ${item.selected ? "selected" : ""}`}
                    aria-pressed={item.selected}
                    title={item.value}
                    onClick={() => narrow(group.facet, item.value)}
                  >
                    <span>{item.value}</span>
                    <small>{item.count}</small>
                  </button>
                ))}
              </div>
            </details>
          ))}
        </aside>
        <div className="case-catalog-results">
          <p className="case-catalog-summary">{summary}</p>
          {results.map((result) => (
            <article key={result.id} className="result-card">
              <span>
                <strong>{result.title}</strong>
                <p>{result.snippet}</p>
                <small>
                  {result.citation}
                  {result.metadata?.county ? ` · ${result.metadata.county}` : ""}
                  {result.metadata?.decisionDate ? ` · ${result.metadata.decisionDate}` : ""}
                </small>
              </span>
              <div className="result-source-actions">
                <SourceFullViewButton citation={result} onOpen={onOpenSource} />
              </div>
            </article>
          ))}
          {hasMore({ total: payload?.total || 0, offset: 0, shown: results.length }) && (
            <button
              className="secondary full"
              type="button"
              disabled={busy}
              onClick={() => load({ offset: results.length })}
            >
              {busy ? <Loader2 className="spin" size={16} /> : null} Show {DEFAULT_PAGE_SIZE} more
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function TreeNode({ node, depth, expandedIds, onToggle, onOpen }) {
  const branch = (node.children || []).length > 0;
  const expanded = expandedIds.includes(node.id);
  return (
    <li className="library-tree-item">
      <div className="library-tree-row" style={{ paddingInlineStart: `${depth * 14}px` }}>
        {branch ? (
          <button
            className="library-tree-toggle"
            type="button"
            aria-expanded={expanded}
            aria-label={`${expanded ? "Collapse" : "Expand"} ${node.label}`}
            onClick={() => onToggle(node.id)}
          >
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
        ) : (
          <span className="library-tree-toggle placeholder" aria-hidden="true" />
        )}
        {node.chunkId ? (
          <button className="library-tree-link" type="button" onClick={() => onOpen(node)}>
            <FileText size={13} /> {node.label}
          </button>
        ) : (
          <span className="library-tree-label">{node.label}</span>
        )}
        {node.citation && <small className="library-tree-citation">{node.citation}</small>}
        {branch && <small className="library-tree-count">{node.count}</small>}
      </div>
      {branch && expanded && (
        <ul className="library-tree">
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              expandedIds={expandedIds}
              onToggle={onToggle}
              onOpen={onOpen}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

function DocumentShelf({ shelf, loading, onOpenSource }) {
  const [selectedSlug, setSelectedSlug] = useState(shelf.documents[0]?.slug || "");
  const [draftFilter, setDraftFilter] = useState("");
  const [contents, setContents] = useState(null);
  const [expandedIds, setExpandedIds] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const activeDocument = useMemo(
    () => shelf.documents.find((item) => item.slug === selectedSlug) || shelf.documents[0] || null,
    [shelf.documents, selectedSlug],
  );

  async function load(slug, filterText) {
    if (!slug) return;
    setBusy(true);
    setError("");
    try {
      const response = await api.libraryDocument(slug, filterText);
      setContents(response);
      setExpandedIds(filterText ? expandedForFilter(response.tree || []) : []);
    } catch (err) {
      setError(err.message || "Could not open this document.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    setDraftFilter("");
    load(activeDocument?.slug, "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeDocument?.slug]);

  if (!shelf.documents.length) {
    // An empty shelf and a shelf that has not arrived yet are different facts.
    return loading
      ? <p className="library-empty"><Loader2 className="spin" size={14} /> Loading the library</p>
      : <p className="library-empty">{shelf.empty}</p>;
  }

  const tree = contents?.tree || [];

  return (
    <div className="library-shelf">
      <div className="library-shelf-documents" role="tablist" aria-label={shelf.label}>
        {shelf.documents.map((item) => (
          <button
            key={item.slug}
            type="button"
            role="tab"
            aria-selected={item.slug === activeDocument?.slug}
            className={`library-document ${item.slug === activeDocument?.slug ? "selected" : ""}`}
            onClick={() => setSelectedSlug(item.slug)}
          >
            <strong>{item.title}</strong>
            <small>{documentSubtitle(item)}</small>
          </button>
        ))}
      </div>
      <form
        className="case-facet-search"
        onSubmit={(event) => {
          event.preventDefault();
          load(activeDocument?.slug, draftFilter.trim());
        }}
      >
        <input
          aria-label={`Filter the contents of ${activeDocument?.title || "this document"}`}
          placeholder="Filter by section heading or citation"
          value={draftFilter}
          onChange={(event) => setDraftFilter(event.target.value)}
        />
        <button className="secondary" type="submit" disabled={busy}>
          {busy ? <Loader2 className="spin" size={14} /> : <Search size={14} />}
        </button>
      </form>
      {error && <div className="inline-error">{error}</div>}
      <p className="library-shelf-summary">
        {contents?.query
          ? `${contents.matchCount} section${contents.matchCount === 1 ? "" : "s"} match "${contents.query}"`
          : `${countSections(tree)} section${countSections(tree) === 1 ? "" : "s"}`}
        {contents?.document?.version ? ` · ${contents.document.version}` : ""}
      </p>
      {!busy && !tree.length && <p className="library-empty">Nothing here matches that filter.</p>}
      <ul className="library-tree root">
        {tree.map((node) => (
          <TreeNode
            key={node.id}
            node={node}
            depth={0}
            expandedIds={expandedIds}
            onToggle={(nodeId) => setExpandedIds((current) => toggleNode(current, nodeId))}
            onOpen={(leaf) => onOpenSource(sectionCitation(contents?.document || activeDocument, leaf))}
          />
        ))}
      </ul>
    </div>
  );
}

/** Reading the corpus without a question: the cases, the treatises, the code. */
export function LibraryBrowser({ onOpenSource }) {
  const [tab, setTab] = useState("cases");
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api.library()
      .then((response) => {
        if (!cancelled) setDocuments(response.documents || []);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "Could not load the content library.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const shelfList = shelves(documents);

  return (
    <section className="library-browser">
      <div className="library-browser-tabs" role="tablist" aria-label="Browse the library">
        {TABS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={tab === item.id}
              className={tab === item.id ? "selected" : ""}
              onClick={() => setTab(item.id)}
            >
              <Icon size={15} /> {item.label}
            </button>
          );
        })}
      </div>
      {error && <div className="inline-error">{error}</div>}
      {tab === "cases" ? (
        <CaseCatalog onOpenSource={onOpenSource} />
      ) : (
        <DocumentShelf
          key={tab}
          shelf={shelfList.find((shelf) => shelf.id === tab)}
          loading={loading}
          onOpenSource={onOpenSource}
        />
      )}
    </section>
  );
}
