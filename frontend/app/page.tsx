"use client";

import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { createJob, getJob, getResults } from "@/lib/api";
import { downloadCsv } from "@/lib/csv";
import { RadiusOption, ResultItem } from "@/types";

const radiusOptions: { label: string; value: RadiusOption }[] = [
  { label: "Bucuresti only", value: "Bucuresti" },
  { label: "50 km", value: "50" },
  { label: "100 km", value: "100" },
  { label: "200 km", value: "200" },
  { label: "All Romania", value: "All Romania" }
];

function currency(price: number | null, unit: string | null): string {
  if (price === null) return "-";
  return `${price} ${unit ?? "RON"}`;
}

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [radiusOption, setRadiusOption] = useState<RadiusOption>("Bucuresti");
  const [includeUnknownLocation, setIncludeUnknownLocation] = useState(false);
  const [maxUrls, setMaxUrls] = useState(80);
  const [timeBudgetSeconds, setTimeBudgetSeconds] = useState(90);
  const [jobId, setJobId] = useState<string | null>(null);

  const [nameFilter, setNameFilter] = useState("");
  const [sizeFilter, setSizeFilter] = useState("");
  const [priceMin, setPriceMin] = useState<string>("");
  const [priceMax, setPriceMax] = useState<string>("");
  const [sortBy, setSortBy] = useState<"price" | "site">("price");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const createJobMutation = useMutation({
    mutationFn: createJob,
    onSuccess: (createdJob) => {
      setJobId(createdJob.id);
    }
  });

  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId!),
    enabled: Boolean(jobId),
    refetchInterval: (queryState) => {
      const status = queryState.state.data?.status;
      return status === "done" || status === "failed" ? false : 2500;
    }
  });

  const resultsQuery = useQuery({
    queryKey: ["results", jobId],
    queryFn: () => getResults(jobId!),
    enabled: Boolean(jobId),
    refetchInterval: jobQuery.data?.status === "running" || jobQuery.data?.status === "queued" ? 4000 : false
  });

  const filteredItems = useMemo(() => {
    const raw = resultsQuery.data?.items ?? [];
    const min = priceMin === "" ? null : Number(priceMin);
    const max = priceMax === "" ? null : Number(priceMax);

    const filtered = raw.filter((item) => {
      if (nameFilter && !item.productName.toLowerCase().includes(nameFilter.toLowerCase())) return false;
      if (sizeFilter && !(item.size ?? "").toLowerCase().includes(sizeFilter.toLowerCase())) return false;
      if (min !== null && item.price !== null && item.price < min) return false;
      if (max !== null && item.price !== null && item.price > max) return false;
      if ((min !== null || max !== null) && item.price === null) return false;
      return true;
    });

    const sorted = [...filtered].sort((a, b) => {
      if (sortBy === "site") {
        const lhs = a.website.toLowerCase();
        const rhs = b.website.toLowerCase();
        return sortDir === "asc" ? lhs.localeCompare(rhs) : rhs.localeCompare(lhs);
      }
      const lhs = a.price ?? Number.POSITIVE_INFINITY;
      const rhs = b.price ?? Number.POSITIVE_INFINITY;
      return sortDir === "asc" ? lhs - rhs : rhs - lhs;
    });

    return sorted;
  }, [resultsQuery.data?.items, nameFilter, sizeFilter, priceMin, priceMax, sortBy, sortDir]);

  function onRadiusChange(next: RadiusOption): void {
    setRadiusOption(next);
    if (next === "Bucuresti") {
      setIncludeUnknownLocation(false);
    } else if (next !== "Bucuresti" && includeUnknownLocation === false) {
      setIncludeUnknownLocation(true);
    }
  }

  function submitSearch(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (!query.trim()) return;

    createJobMutation.mutate({
      query: query.trim(),
      radiusOption,
      includeUnknownLocation,
      maxUrls,
      timeBudgetSeconds
    });
  }

  const isRunning = jobQuery.data?.status === "running" || jobQuery.data?.status === "queued";

  return (
    <main className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-4 py-8 text-ink sm:px-6 lg:px-10">
      <header className="panel">
        <p className="text-xs uppercase tracking-[0.22em] text-accent">Romanian Product Discovery</p>
        <h1 className="mt-2 font-heading text-3xl font-bold sm:text-4xl">Discover and scrape products across Romania</h1>
        <p className="mt-3 max-w-3xl text-sm text-ink/80">
          Enter a product query, choose distance from Bucuresti, and track scraping progress while results stream in.
        </p>
      </header>

      <section className="panel">
        <form className="grid gap-4 lg:grid-cols-6" onSubmit={submitSearch}>
          <label className="lg:col-span-2">
            <span className="mb-1 block text-xs font-semibold uppercase text-ink/70">Product query</span>
            <input
              className="field"
              placeholder="trandafir catarator, ghiveci 30cm..."
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>

          <label>
            <span className="mb-1 block text-xs font-semibold uppercase text-ink/70">Radius</span>
            <select
              className="field"
              value={radiusOption}
              onChange={(event) => onRadiusChange(event.target.value as RadiusOption)}
            >
              {radiusOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span className="mb-1 block text-xs font-semibold uppercase text-ink/70">Max sites</span>
            <input
              className="field"
              type="number"
              min={20}
              max={200}
              value={maxUrls}
              onChange={(event) => setMaxUrls(Number(event.target.value))}
            />
          </label>

          <label>
            <span className="mb-1 block text-xs font-semibold uppercase text-ink/70">Time budget (sec)</span>
            <input
              className="field"
              type="number"
              min={60}
              max={180}
              value={timeBudgetSeconds}
              onChange={(event) => setTimeBudgetSeconds(Number(event.target.value))}
            />
          </label>

          <div className="flex items-end">
            <button
              className="btn btn-primary w-full"
              type="submit"
              disabled={createJobMutation.isPending || !query.trim()}
            >
              {createJobMutation.isPending ? "Creating job..." : "Search"}
            </button>
          </div>

          <label className="col-span-full flex items-center gap-3 rounded-lg border border-ink/10 bg-base px-3 py-2 text-sm">
            <input
              type="checkbox"
              checked={includeUnknownLocation}
              onChange={(event) => setIncludeUnknownLocation(event.target.checked)}
            />
            Include unknown location
          </label>
        </form>

        {createJobMutation.isError && (
          <p className="mt-3 rounded-lg bg-warn/10 px-3 py-2 text-sm text-warn">
            {(createJobMutation.error as Error).message}
          </p>
        )}
      </section>

      <section className="panel">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-heading text-xl">Job progress</h2>
          {jobQuery.data && <p className="text-sm font-medium uppercase text-ink/70">{jobQuery.data.status}</p>}
        </div>
        {!jobId && <p className="mt-3 text-sm text-ink/70">Create a job to start scraping.</p>}
        {jobQuery.data && (
          <>
            <div className="mt-4 h-3 overflow-hidden rounded-full bg-ink/10">
              <div
                className="h-full rounded-full bg-accent transition-all duration-300"
                style={{ width: `${jobQuery.data.progress}%` }}
              />
            </div>
            <div className="mt-3 grid gap-2 text-sm text-ink/75 sm:grid-cols-4">
              <p>Candidates: {jobQuery.data.totalCandidateUrls}</p>
              <p>Processed: {jobQuery.data.processedUrls}</p>
              <p>Found products: {jobQuery.data.foundProducts}</p>
              <p>Errors: {jobQuery.data.errors}</p>
            </div>
            {jobQuery.data.errorMessage && (
              <p className="mt-3 rounded-lg bg-warn/10 px-3 py-2 text-sm text-warn">{jobQuery.data.errorMessage}</p>
            )}
          </>
        )}
      </section>

      <section className="panel">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-heading text-xl">Results</h2>
          <div className="flex gap-2">
            <button
              className="btn btn-ghost"
              onClick={() => downloadCsv(filteredItems, "product-results.csv")}
              disabled={filteredItems.length === 0}
            >
              Download CSV
            </button>
          </div>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-6">
          <input
            className="field md:col-span-2"
            placeholder="Filter product"
            value={nameFilter}
            onChange={(event) => setNameFilter(event.target.value)}
          />
          <input
            className="field"
            placeholder="Price min"
            type="number"
            value={priceMin}
            onChange={(event) => setPriceMin(event.target.value)}
          />
          <input
            className="field"
            placeholder="Price max"
            type="number"
            value={priceMax}
            onChange={(event) => setPriceMax(event.target.value)}
          />
          <input
            className="field"
            placeholder="Filter size"
            value={sizeFilter}
            onChange={(event) => setSizeFilter(event.target.value)}
          />
          <div className="grid grid-cols-2 gap-2">
            <select className="field" value={sortBy} onChange={(event) => setSortBy(event.target.value as "price" | "site")}>
              <option value="price">Sort price</option>
              <option value="site">Sort site</option>
            </select>
            <select className="field" value={sortDir} onChange={(event) => setSortDir(event.target.value as "asc" | "desc")}>
              <option value="asc">Asc</option>
              <option value="desc">Desc</option>
            </select>
          </div>
        </div>

        {isRunning && <p className="mt-4 text-sm text-ink/70">Scraping in background. Results update automatically.</p>}
        {resultsQuery.isLoading && <p className="mt-4 text-sm text-ink/70">Loading results...</p>}
        {resultsQuery.isError && (
          <p className="mt-4 rounded-lg bg-warn/10 px-3 py-2 text-sm text-warn">
            {(resultsQuery.error as Error).message}
          </p>
        )}

        {!resultsQuery.isLoading && filteredItems.length === 0 && (
          <p className="mt-4 text-sm text-ink/70">No results yet. Try a broader query or larger radius.</p>
        )}

        {filteredItems.length > 0 && (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full table-auto border-collapse text-sm">
              <thead>
                <tr className="border-b border-ink/15 text-left text-xs uppercase tracking-wide text-ink/70">
                  <th className="px-2 py-2">Product</th>
                  <th className="px-2 py-2">Website</th>
                  <th className="px-2 py-2">Price</th>
                  <th className="px-2 py-2">Size</th>
                  <th className="px-2 py-2">Location</th>
                  <th className="px-2 py-2">Link</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item: ResultItem) => (
                  <tr key={item.id} className="border-b border-ink/10 align-top">
                    <td className="px-2 py-3">{item.productName}</td>
                    <td className="px-2 py-3">{item.website}</td>
                    <td className="px-2 py-3">{currency(item.price, item.currency)}</td>
                    <td className="px-2 py-3">{item.size ?? "-"}</td>
                    <td className="px-2 py-3">
                      {item.locationUnknown
                        ? "Unknown"
                        : `${item.locationCity ?? "Romania"}${item.distanceKm ? ` (${item.distanceKm} km)` : ""}`}
                    </td>
                    <td className="px-2 py-3">
                      <a className="text-accent underline" href={item.sourceUrl} target="_blank" rel="noreferrer">
                        Open source
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
