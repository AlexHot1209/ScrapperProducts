"use client";

import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { createJob, getJob, getResults } from "@/lib/api";
import { downloadCsv } from "@/lib/csv";
import { RadiusOption, ResultItem } from "@/types";

const radiusOptions: { label: string; value: RadiusOption }[] = [
  { label: "Doar Bucuresti", value: "Bucuresti" },
  { label: "50 km", value: "50" },
  { label: "100 km", value: "100" },
  { label: "200 km", value: "200" },
  { label: "Toata Romania", value: "All Romania" }
];

function currency(price: number | null, unit: string | null): string {
  if (price === null) return "-";
  return `${price} ${unit ?? "RON"}`;
}

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [radiusOption, setRadiusOption] = useState<RadiusOption>("Bucuresti");
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

  function submitSearch(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (!query.trim()) return;

    const includeUnknownLocation = radiusOption !== "Bucuresti";

    createJobMutation.mutate({
      query: query.trim(),
      radiusOption,
      includeUnknownLocation,
      maxUrls: 80,
      timeBudgetSeconds: 90
    });
  }

  const isRunning = jobQuery.data?.status === "running" || jobQuery.data?.status === "queued";

  return (
    <main className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-4 py-8 text-ink sm:px-6 lg:px-10">
      <header className="panel">
        <p className="text-xs uppercase tracking-[0.22em] text-accent">Mythos Garden</p>
        <h1 className="mt-2 font-heading text-3xl font-bold sm:text-4xl">Cautare dinamica de produse</h1>
      </header>

      <section className="panel">
        <form className="grid gap-4 md:grid-cols-3 lg:grid-cols-4" onSubmit={submitSearch}>
          <label className="lg:col-span-2">
            <span className="mb-1 block text-xs font-semibold uppercase text-ink/70">Cautare produs</span>
            <input
              className="field"
              placeholder="trandafir catarator, ghiveci 30cm..."
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>

          <label>
            <span className="mb-1 block text-xs font-semibold uppercase text-ink/70">Distanta</span>
            <select
              className="field"
              value={radiusOption}
              onChange={(event) => setRadiusOption(event.target.value as RadiusOption)}
            >
              {radiusOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <div className="flex items-end">
            <button
              className="btn btn-primary w-full"
              type="submit"
              disabled={createJobMutation.isPending || !query.trim()}
            >
              {createJobMutation.isPending ? "Se porneste cautarea..." : "Cauta"}
            </button>
          </div>
        </form>

        {createJobMutation.isError && (
          <p className="mt-3 rounded-lg bg-warn/10 px-3 py-2 text-sm text-warn">
            {(createJobMutation.error as Error).message}
          </p>
        )}
      </section>

      <section className="panel">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-heading text-xl">Rezultate</h2>
          <div className="flex gap-2">
            <button
              className="btn btn-ghost"
              onClick={() => downloadCsv(filteredItems, "rezultate-produse.csv")}
              disabled={filteredItems.length === 0}
            >
              Descarca CSV
            </button>
          </div>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-6">
          <input
            className="field md:col-span-2"
            placeholder="Filtreaza produs"
            value={nameFilter}
            onChange={(event) => setNameFilter(event.target.value)}
          />
          <input
            className="field"
            placeholder="Pret minim"
            type="number"
            value={priceMin}
            onChange={(event) => setPriceMin(event.target.value)}
          />
          <input
            className="field"
            placeholder="Pret maxim"
            type="number"
            value={priceMax}
            onChange={(event) => setPriceMax(event.target.value)}
          />
          <input
            className="field"
            placeholder="Filtreaza marime"
            value={sizeFilter}
            onChange={(event) => setSizeFilter(event.target.value)}
          />
          <div className="grid grid-cols-2 gap-2">
            <select className="field" value={sortBy} onChange={(event) => setSortBy(event.target.value as "price" | "site")}>
              <option value="price">Sorteaza dupa pret</option>
              <option value="site">Sorteaza dupa site</option>
            </select>
            <select className="field" value={sortDir} onChange={(event) => setSortDir(event.target.value as "asc" | "desc")}>
              <option value="asc">Crescator</option>
              <option value="desc">Descrescator</option>
            </select>
          </div>
        </div>

        {isRunning && <p className="mt-4 text-sm text-ink/70">Se colecteaza in fundal. Rezultatele se actualizeaza automat.</p>}
        {resultsQuery.isLoading && <p className="mt-4 text-sm text-ink/70">Se incarca rezultatele...</p>}
        {resultsQuery.isError && (
          <p className="mt-4 rounded-lg bg-warn/10 px-3 py-2 text-sm text-warn">
            {(resultsQuery.error as Error).message}
          </p>
        )}

        {!resultsQuery.isLoading && filteredItems.length === 0 && (
          <p className="mt-4 text-sm text-ink/70">Inca nu sunt rezultate. Incearca o cautare mai larga sau o distanta mai mare.</p>
        )}

        {filteredItems.length > 0 && (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full table-auto border-collapse text-sm">
              <thead>
                <tr className="border-b border-ink/15 text-left text-xs uppercase tracking-wide text-ink/70">
                  <th className="px-2 py-2">Produs</th>
                  <th className="px-2 py-2">Site</th>
                  <th className="px-2 py-2">Pret</th>
                  <th className="px-2 py-2">Marime</th>
                  <th className="px-2 py-2">Locatie</th>
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
                        ? "Necunoscut"
                        : `${item.locationCity ?? "Romania"}${item.distanceKm ? ` (${item.distanceKm} km)` : ""}`}
                    </td>
                    <td className="px-2 py-3">
                      <a className="text-accent underline" href={item.sourceUrl} target="_blank" rel="noreferrer">
                        Deschide sursa
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
