import { useMemo, useState } from "react";
import { BarChart3, Filter, Upload, FileDown } from "lucide-react";
import RestaurantCard from "./components/RestaurantCard";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

export default function App() {
  const [restaurants, setRestaurants] = useState([]);
  const [bairros, setBairros] = useState([]);
  const [selectedBairro, setSelectedBairro] = useState("Todos");
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [downloadingContacts, setDownloadingContacts] = useState(false);
  const [error, setError] = useState("");

  const filteredRestaurants = useMemo(() => {
    if (selectedBairro === "Todos") return restaurants;
    return restaurants.filter((r) => r.bairro?.toLowerCase() === selectedBairro.toLowerCase());
  }, [restaurants, selectedBairro]);

  const opportunityStats = useMemo(() => {
    return filteredRestaurants.reduce(
      (acc, current) => {
        const key = current.oportunidade || "Bronze";
        acc[key] = (acc[key] || 0) + 1;
        return acc;
      },
      { Ouro: 0, Prata: 0, Bronze: 0 }
    );
  }, [filteredRestaurants]);

  async function extractErrorMessage(response, fallbackMessage) {
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const payload = await response.json();
      return payload?.detail || fallbackMessage;
    }

    const text = await response.text();
    return text || fallbackMessage;
  }

  async function handleUpload() {
    if (!file) {
      setError("Selecione um arquivo CSV ou XLSX antes de processar.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const message = await extractErrorMessage(response, "Falha ao processar planilha");
        throw new Error(message || "Falha ao processar planilha");
      }

      const payload = await response.json();
      setRestaurants(payload.data || []);
      setBairros(["Todos", ...(payload.bairros || [])]);
      setSelectedBairro("Todos");
    } catch (err) {
      setError(err.message || "Erro inesperado no upload.");
    } finally {
      setLoading(false);
    }
  }

  async function handleGlobalPdf() {
    if (!restaurants.length) {
      setError("Carregue uma planilha antes de gerar o relatorio PDF.");
      return;
    }

    setDownloadingPdf(true);
    setError("");
    try {
      const query = selectedBairro !== "Todos" ? `?bairro=${encodeURIComponent(selectedBairro)}` : "";
      const response = await fetch(`${API_BASE}/report${query}`);
      if (!response.ok) {
        const message = await extractErrorMessage(response, "Falha ao gerar PDF consolidado");
        throw new Error(message || "Falha ao gerar PDF consolidado");
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `relatorio-consolidado-${selectedBairro.toLowerCase().replace(/\s+/g, "-")}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || "Erro ao baixar relatorio PDF.");
    } finally {
      setDownloadingPdf(false);
    }
  }

  async function handleRestaurantPdf(restaurantId, restaurantName) {
    setError("");
    try {
      const response = await fetch(`${API_BASE}/report/${restaurantId}`);
      if (!response.ok) {
        const message = await extractErrorMessage(response, "Falha ao gerar PDF do restaurante");
        throw new Error(message || "Falha ao gerar PDF do restaurante");
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      const normalizedName = (restaurantName || "restaurante").toLowerCase().replace(/[^a-z0-9]+/g, "-");
      anchor.download = `relatorio-${normalizedName}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || "Erro ao baixar relatorio individual.");
    }
  }

  async function handleContactsExport() {
    if (!restaurants.length) {
      setError("Carregue uma planilha antes de exportar os contatos.");
      return;
    }

    setDownloadingContacts(true);
    setError("");
    try {
      const query = selectedBairro !== "Todos" ? `?bairro=${encodeURIComponent(selectedBairro)}` : "";
      const response = await fetch(`${API_BASE}/contacts/export${query}`);
      if (!response.ok) {
        const message = await extractErrorMessage(response, "Falha ao exportar cadencia de contatos");
        throw new Error(message || "Falha ao exportar cadencia de contatos");
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `cadencia-contatos-${selectedBairro.toLowerCase().replace(/\s+/g, "-")}.csv`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || "Erro ao exportar contatos.");
    } finally {
      setDownloadingContacts(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="mb-8 rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-900 via-zinc-900 to-slate-800 p-6 shadow-xl">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-cyan-700/60 bg-cyan-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-300">
                <BarChart3 size={14} />
                Dashboard de Prospeccao Local
              </div>
              <h1 className="text-2xl font-bold text-white sm:text-3xl">Restaurantes de Manaus</h1>
              <p className="mt-2 text-sm text-slate-300">
                Analise de Site, Google Meu Negocio e Contato para identificar oportunidades comerciais.
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                onClick={handleContactsExport}
                disabled={downloadingContacts}
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-200 transition hover:bg-emerald-500/20 disabled:opacity-60"
              >
                <Upload size={16} />
                {downloadingContacts ? "Exportando..." : "Exportar Cadencia CSV"}
              </button>

              <button
                onClick={handleGlobalPdf}
                disabled={downloadingPdf}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-900 transition hover:bg-cyan-400 disabled:opacity-60"
              >
                <FileDown size={16} />
                {downloadingPdf ? "Gerando PDF..." : "Gerar Relatorio PDF"}
              </button>
            </div>
          </div>
        </header>

        <section className="mb-6 grid gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-4 md:grid-cols-[1fr_auto_auto]">
          <label className="flex items-center gap-3 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2">
            <Upload size={16} className="text-cyan-300" />
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="w-full text-sm text-slate-200 file:mr-3 file:rounded-md file:border-0 file:bg-slate-700 file:px-3 file:py-1.5 file:text-slate-100"
            />
          </label>

          <div className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm">
            <Filter size={16} className="text-amber-300" />
            <select
              value={selectedBairro}
              onChange={(e) => setSelectedBairro(e.target.value)}
              className="w-full bg-transparent text-slate-100 outline-none"
            >
              {(bairros.length ? bairros : ["Todos"]).map((bairro) => (
                <option key={bairro} value={bairro} className="bg-slate-900">
                  {bairro}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleUpload}
            disabled={loading}
            className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:opacity-60"
          >
            {loading ? "Processando..." : "Processar Planilha"}
          </button>
        </section>

        {error && (
          <div className="mb-6 rounded-lg border border-rose-500/50 bg-rose-500/10 p-3 text-sm text-rose-200">
            {error}
          </div>
        )}

        <section className="mb-4 flex items-center justify-between text-sm text-slate-300">
          <p>Total exibido: {filteredRestaurants.length}</p>
          <p>Bairro: {selectedBairro}</p>
        </section>

        <section className="mb-6 grid gap-3 md:grid-cols-3">
          <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-emerald-300">Ouro</p>
            <p className="mt-1 text-2xl font-bold text-white">{opportunityStats.Ouro}</p>
            <p className="text-xs text-emerald-200">Site fraco ou ausente com alto potencial</p>
          </div>
          <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-300">Prata</p>
            <p className="mt-1 text-2xl font-bold text-white">{opportunityStats.Prata}</p>
            <p className="text-xs text-amber-200">Google Meu Negocio com sinais de ajuste</p>
          </div>
          <div className="rounded-xl border border-sky-500/40 bg-sky-500/10 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-sky-300">Bronze</p>
            <p className="mt-1 text-2xl font-bold text-white">{opportunityStats.Bronze}</p>
            <p className="text-xs text-sky-200">Presenca digital mais estavel</p>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filteredRestaurants.map((restaurant) => (
            <RestaurantCard
              key={restaurant.id}
              restaurant={restaurant}
              onGeneratePdf={() => handleRestaurantPdf(restaurant.id, restaurant.nome)}
            />
          ))}
        </section>
      </div>
    </div>
  );
}
