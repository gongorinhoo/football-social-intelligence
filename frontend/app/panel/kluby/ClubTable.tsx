"use client";

import { useMemo, useState } from "react";

type Club = {
  id: number;
  name: string;
  tiktok_handle: string;
  league: string | null;
  is_active: boolean;
};

type Props = {
  clubs: Club[];
};

export default function ClubTable({ clubs }: Props) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [league, setLeague] = useState("all");

  const leagues = useMemo(
    () =>
      Array.from(
        new Set(
          clubs
            .map((club) => club.league)
            .filter((value): value is string => Boolean(value))
        )
      ).sort(),
    [clubs]
  );

  const filteredClubs = useMemo(() => {
    return clubs.filter((club) => {
      const query = search.toLowerCase().trim();

      const matchesSearch =
        club.name.toLowerCase().includes(query) ||
        club.tiktok_handle.toLowerCase().includes(query);

      const matchesStatus =
        status === "all" ||
        (status === "active" && club.is_active) ||
        (status === "inactive" && !club.is_active);

      const matchesLeague =
        league === "all" ||
        (league === "unassigned" && !club.league) ||
        club.league === league;

      return matchesSearch && matchesStatus && matchesLeague;
    });
  }, [clubs, search, status, league]);

  const activeCount = clubs.filter((club) => club.is_active).length;

  return (
    <div className="space-y-6">
      {/* Statystyki */}
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-white/10 bg-[#111923] p-5">
          <p className="text-sm text-slate-400">Wszystkie kluby</p>
          <p className="mt-2 text-3xl font-semibold">{clubs.length}</p>
        </div>

        <div className="rounded-xl border border-white/10 bg-[#111923] p-5">
          <p className="text-sm text-slate-400">Aktywne profile</p>
          <p className="mt-2 text-3xl font-semibold text-emerald-400">
            {activeCount}
          </p>
        </div>

        <div className="rounded-xl border border-white/10 bg-[#111923] p-5">
          <p className="text-sm text-slate-400">Wyniki wyszukiwania</p>
          <p className="mt-2 text-3xl font-semibold">
            {filteredClubs.length}
          </p>
        </div>
      </div>

      {/* Filtry */}
      <div className="grid gap-3 md:grid-cols-3">
        <input
          type="text"
          placeholder="Szukaj klubu lub TikTok handle..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="rounded-lg border border-white/10 bg-[#111923] px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-emerald-500"
        />

        <select
          value={status}
          onChange={(event) => setStatus(event.target.value)}
          className="rounded-lg border border-white/10 bg-[#111923] px-4 py-3 text-sm text-white outline-none focus:border-emerald-500"
        >
          <option value="all">Wszystkie statusy</option>
          <option value="active">Aktywne</option>
          <option value="inactive">Nieaktywne</option>
        </select>

        <select
          value={league}
          onChange={(event) => setLeague(event.target.value)}
          className="rounded-lg border border-white/10 bg-[#111923] px-4 py-3 text-sm text-white outline-none focus:border-emerald-500"
        >
          <option value="all">Wszystkie ligi</option>
          <option value="unassigned">Nieprzypisana liga</option>

          {leagues.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>

      {/* Tabela */}
      <div className="overflow-hidden rounded-xl border border-white/10 bg-[#111923]">
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
          <h2 className="font-semibold">Monitorowane kluby</h2>
          <span className="text-xs text-slate-500">
            {filteredClubs.length} rekordów
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-white/[0.03] text-xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-5 py-4">ID</th>
                <th className="px-5 py-4">Klub</th>
                <th className="px-5 py-4">TikTok</th>
                <th className="px-5 py-4">Liga</th>
                <th className="px-5 py-4">Status</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-white/5">
              {filteredClubs.map((club) => (
                <tr
                  key={club.id}
                  className="transition hover:bg-white/[0.03]"
                >
                  <td className="px-5 py-4 text-slate-500">
                    #{club.id}
                  </td>

                  <td className="px-5 py-4 font-medium text-white">
                    {club.name}
                  </td>

                  <td className="px-5 py-4">
                    <a
                      href={`https://www.tiktok.com/@${encodeURIComponent(
                        club.tiktok_handle
                      )}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-emerald-400 hover:text-emerald-300"
                    >
                      @{club.tiktok_handle}
                    </a>
                  </td>

                  <td className="px-5 py-4 text-slate-400">
                    {club.league || "Nieprzypisana"}
                  </td>

                  <td className="px-5 py-4">
                    {club.is_active ? (
                      <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-400">
                        ● Aktywny
                      </span>
                    ) : (
                      <span className="rounded-full border border-slate-500/20 bg-slate-500/10 px-3 py-1 text-xs text-slate-400">
                        ● Nieaktywny
                      </span>
                    )}
                  </td>
                </tr>
              ))}

              {filteredClubs.length === 0 && (
                <tr>
                  <td
                    colSpan={5}
                    className="px-5 py-12 text-center text-slate-500"
                  >
                    Nie znaleziono klubów spełniających kryteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
