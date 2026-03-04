import { ResultItem } from "@/types";

function escapeCell(value: string): string {
  const escaped = value.replace(/"/g, "\"\"");
  return `"${escaped}"`;
}

export function downloadCsv(rows: ResultItem[], fileName = "rezultate.csv"): void {
  const header = [
    "Produs",
    "Site",
    "Pret",
    "Moneda",
    "Marime",
    "Oras locatie",
    "Adresa locatie",
    "Distanta km",
    "URL"
  ];
  const lines = rows.map((row) =>
    [
      row.productName,
      row.website,
      row.price?.toString() ?? "",
      row.currency ?? "",
      row.size ?? "",
      row.locationCity ?? "",
      row.locationAddress ?? "",
      row.distanceKm?.toString() ?? "",
      row.sourceUrl
    ]
      .map((cell) => escapeCell(cell))
      .join(",")
  );

  const csv = [header.join(","), ...lines].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.setAttribute("download", fileName);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
