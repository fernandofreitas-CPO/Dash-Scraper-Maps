import { Globe, MapPinned, MessageCircle, Phone, Star, FileDown } from "lucide-react";

function badgeTone(status) {
  if (["Ativo", "Alta", "Ouro", "Bom"].includes(status)) {
    return "bg-emerald-500/15 text-emerald-300 border-emerald-500/40";
  }
  if (["Media", "Prata", "Medio", "Necessita Validacao"].includes(status)) {
    return "bg-amber-500/15 text-amber-300 border-amber-500/40";
  }
  return "bg-rose-500/15 text-rose-300 border-rose-500/40";
}

function siteHealth(site) {
  if (!site?.has_website) return "Critico";
  if (site.score >= 70) return "Bom";
  if (site.score >= 45) return "Medio";
  return "Critico";
}

function toWhatsAppUrl(restaurant) {
  const phone = restaurant?.contato?.telefone || restaurant?.telefone || "";
  const message = encodeURIComponent(restaurant?.whatsapp_message || "Ola! Tenho uma proposta para melhorar sua presenca digital.");
  return `https://wa.me/55${phone}?text=${message}`;
}

function channelLabel(channel) {
  if (channel === "whatsapp") return "WhatsApp";
  if (channel === "telefone") return "Telefone";
  if (channel === "central") return "Central";
  return "Contato";
}

function primaryTarget(restaurant) {
  const targets = restaurant?.contato?.targets || [];
  return targets.find((target) => target.canal === "whatsapp" && target.status === "Ativo") || targets[0] || null;
}

function rankingLabel(gmn) {
  if (!gmn?.ranking_position) return "Nao mapeado";
  return `#${gmn.ranking_position}`;
}

export default function RestaurantCard({ restaurant, onGeneratePdf }) {
  const siteStatus = siteHealth(restaurant.site);
  const contactTargets = restaurant?.contato?.targets || [];
  const leadTarget = primaryTarget(restaurant);

  return (
    <article className="group rounded-2xl border border-slate-800 bg-slate-900/80 p-4 shadow-lg transition hover:-translate-y-1 hover:border-cyan-600/60">
      <header className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-white">{restaurant.nome}</h3>
          <p className="mt-1 text-xs text-slate-400">{restaurant.endereco || "Endereco nao informado"}</p>
        </div>
        <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${badgeTone(restaurant.oportunidade)}`}>
          {restaurant.oportunidade}
        </span>
      </header>

      <div className="mb-3 flex flex-wrap gap-2 text-xs">
        <span className={`rounded-full border px-2.5 py-1 ${badgeTone(siteStatus)}`}>Site: {siteStatus}</span>
        <span className={`rounded-full border px-2.5 py-1 ${badgeTone(restaurant.contato?.status)}`}>
          Contato: {restaurant.contato?.status}
        </span>
        <span className={`rounded-full border px-2.5 py-1 ${badgeTone(restaurant.gmn?.response_rate)}`}>
          GMN: {restaurant.gmn?.response_rate}
        </span>
      </div>

      <div className="space-y-2 text-sm text-slate-300">
        <p className="flex items-center gap-2">
          <MapPinned size={15} className="text-cyan-300" />
          {restaurant.bairro || "Bairro nao informado"}
        </p>
        <p className="flex items-center gap-2">
          <Phone size={15} className="text-cyan-300" />
          {restaurant.contato?.telefone_display || restaurant.telefone || "Telefone nao informado"}
        </p>
        <p className="flex items-center gap-2">
          <Globe size={15} className="text-cyan-300" />
          {restaurant.website || "Sem website"}
        </p>
        <p className="flex items-center gap-2">
          <Star size={15} className="text-amber-300" />
          {restaurant.gmn?.stars?.toFixed?.(1) || "0.0"} estrelas - {restaurant.gmn?.reviews || 0} avaliacoes
        </p>
        <p className="text-xs text-slate-400">
          Ranking local: {rankingLabel(restaurant.gmn)} | Fonte: {restaurant.gmn?.source || "planilha"}
        </p>
        <p className="text-xs text-slate-400">
          IA: {restaurant.integrations?.openai ? "OpenAI" : "Regra local"} | Serper: {restaurant.integrations?.serper ? "ativo" : "inativo"}
        </p>
      </div>

      <div className="mt-4 rounded-lg border border-slate-700 bg-slate-950/60 p-3">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Contatos acionaveis</p>
        <div className="space-y-2">
          {contactTargets.length ? (
            contactTargets.map((target, index) => (
              <div key={`${target.numero}-${index}`} className="flex items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2">
                <div>
                  <p className="text-sm font-medium text-slate-100">{target.display || target.numero}</p>
                  <p className="text-xs text-slate-400">
                    {channelLabel(target.canal)} | {target.status}
                  </p>
                </div>

                {target.action_url ? (
                  <a
                    href={target.action_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center justify-center gap-2 rounded-lg bg-slate-800 px-3 py-2 text-xs font-semibold text-slate-100 transition hover:bg-slate-700"
                  >
                    {target.canal === "whatsapp" ? <MessageCircle size={14} /> : <Phone size={14} />}
                    {target.canal === "whatsapp" ? "Enviar" : "Ligar"}
                  </a>
                ) : (
                  <span className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-500">Validar</span>
                )}
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-400">Nenhum contato acionavel identificado na planilha.</p>
          )}
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-slate-700 bg-slate-950/60 p-3">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Pontos de melhoria (IA)</p>
        <ul className="space-y-1 text-sm text-slate-200">
          {(restaurant.gmn?.improvements || []).map((item, index) => (
            <li key={index}>- {item}</li>
          ))}
        </ul>
      </div>

      {!restaurant.site?.has_website && restaurant.site?.pitch && (
        <div className="mt-3 rounded-lg border border-amber-500/50 bg-amber-500/10 p-3 text-sm text-amber-200">
          {restaurant.site.pitch}
        </div>
      )}

      <footer className="mt-4 grid grid-cols-2 gap-2">
        {leadTarget?.action_url ? (
          <a
            href={leadTarget.canal === "whatsapp" ? toWhatsAppUrl(restaurant) : leadTarget.action_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-500 px-3 py-2 text-xs font-semibold text-slate-950 transition hover:bg-emerald-400"
          >
            {leadTarget.canal === "whatsapp" ? <MessageCircle size={14} /> : <Phone size={14} />}
            {leadTarget.canal === "whatsapp" ? "WhatsApp Pitch" : `Ligar ${channelLabel(leadTarget.canal)}`}
          </a>
        ) : (
          <button
            disabled
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-slate-800 px-3 py-2 text-xs font-semibold text-slate-500"
          >
            <Phone size={14} />
            Sem contato direto
          </button>
        )}

        <button
          onClick={onGeneratePdf}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-cyan-500 px-3 py-2 text-xs font-semibold text-slate-900 transition hover:bg-cyan-400"
        >
          <FileDown size={14} />
          PDF
        </button>
      </footer>
    </article>
  );
}
