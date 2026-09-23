import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

const dateKey = (date) => [
  date.getFullYear(),
  String(date.getMonth() + 1).padStart(2, "0"),
  String(date.getDate()).padStart(2, "0"),
].join("-");

const parseLocalDate = (value) => {
  const [year, month, day] = String(value || "").split("-").map(Number);
  return new Date(year, month - 1, day, 12);
};

const dayTone = (day) => {
  if (!day || day.status === "future") return "empty";
  const allowed = Number(day.available_today || 0);
  const used = Number(day.used_today || 0);
  const remaining = Number(day.remaining_today ?? allowed - used);
  if (remaining < 0 || used > allowed) return "over";
  if (allowed > 0 && remaining <= allowed * 0.3) return "near";
  return "safe";
};

export default function PulseCalendar({
  days = [],
  selectedDate,
  onSelect,
  language = "en",
  tone = "dark",
  amountsHidden = false,
}) {
  const locale = language === "ar" ? "ar-EG" : "en-US";
  const initialDate = selectedDate || [...days].reverse().find((day) => day.status !== "future")?.date || days[0]?.date;
  const baseMonth = initialDate ? parseLocalDate(initialDate) : new Date();
  const [monthOffset, setMonthOffset] = useState(0);
  const visibleMonth = new Date(
    baseMonth.getFullYear(),
    baseMonth.getMonth() + monthOffset,
    1,
    12
  );

  const daysByDate = new Map(days.map((day) => [day.date, day]));
  const year = visibleMonth.getFullYear();
  const month = visibleMonth.getMonth();
  const totalDays = new Date(year, month + 1, 0, 12).getDate();
  const cells = Array.from({ length: totalDays }, (_, index) => {
    const date = new Date(year, month, index + 1, 12);
    const key = dateKey(date);
    return { date, key, data: daysByDate.get(key) || null };
  });
  const paddedCells = [
    ...cells,
    ...Array.from({ length: (7 - (cells.length % 7)) % 7 }, () => null),
  ];
  const weeks = Array.from(
    { length: paddedCells.length / 7 },
    (_, index) => paddedCells.slice(index * 7, (index + 1) * 7)
  );

  const today = dateKey(new Date());

  return (
    <section className={`pulse-calendar pulse-calendar-${tone}`} aria-label="Daily spending calendar">
      <header>
        <button type="button" onClick={() => setMonthOffset((offset) => offset - 1)} aria-label="Previous month">
          <ChevronLeft size={18} />
        </button>
        <strong>{new Intl.DateTimeFormat(locale, { month: "long", year: "numeric" }).format(visibleMonth)}</strong>
        <button type="button" onClick={() => setMonthOffset((offset) => offset + 1)} aria-label="Next month">
          <ChevronRight size={18} />
        </button>
      </header>
      <div className="pulse-calendar-weeks">
        {weeks.map((week, weekIndex) => {
          const datedCells = week.filter(Boolean);
          const firstDay = datedCells[0]?.date.getDate();
          const lastDay = datedCells.at(-1)?.date.getDate();
          const weekUsed = datedCells.reduce(
            (total, cell) => total + Number(cell.data?.used_today || 0),
            0
          );
          const hasWeekData = datedCells.some(
            (cell) => cell.data && cell.data.status !== "future"
          );

          return (
            <div className="pulse-calendar-week" key={`${year}-${month}-${weekIndex}`}>
              <span className="pulse-calendar-range" aria-hidden="true">
                {firstDay === lastDay ? firstDay : `${firstDay}-${lastDay}`}
              </span>
              <div className="pulse-calendar-grid">
                {week.map((cell, index) => {
                  if (!cell) return <span className="pulse-calendar-blank" key={`blank-${weekIndex}-${index}`} />;
                  const state = dayTone(cell.data);
                  const isSelected = cell.key === selectedDate;
                  const isToday = cell.key === today;
                  const used = Number(cell.data?.used_today || 0);
                  const allowed = Number(cell.data?.available_today || 0);
                  const stateLabel = state === "over" ? "over allowance" : state === "near" ? "near allowance" : state === "safe" ? "within allowance" : "no data";
                  return (
                    <button
                      key={cell.key}
                      type="button"
                      className={`pulse-calendar-day is-${state} ${isSelected ? "is-selected" : ""} ${isToday ? "is-today" : ""}`}
                      disabled={!cell.data || cell.data.status === "future"}
                      onClick={() => {
                        if (!cell.data) return;
                        setMonthOffset(0);
                        onSelect?.(cell.data);
                      }}
                      aria-pressed={isSelected}
                      aria-label={amountsHidden
                        ? `${new Intl.DateTimeFormat(locale, { dateStyle: "long" }).format(cell.date)}, ${stateLabel}, amounts hidden`
                        : `${new Intl.DateTimeFormat(locale, { dateStyle: "long" }).format(cell.date)}, ${stateLabel}, used EGP ${used}, allowance EGP ${allowed}`}
                    >
                      <span>{new Intl.NumberFormat(locale).format(cell.date.getDate())}</span>
                    </button>
                  );
                })}
              </div>
              <span className="pulse-calendar-week-total">
                <small>{hasWeekData ? "Used" : "No data"}</small>
                <strong>{hasWeekData ? `EGP ${new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(weekUsed)}` : "-"}</strong>
              </span>
            </div>
          );
        })}
      </div>
      <div className="pulse-calendar-legend" aria-hidden="true">
        <span><i className="is-safe" />Within</span>
        <span><i className="is-near" />Near</span>
        <span><i className="is-over" />Over</span>
      </div>
    </section>
  );
}
