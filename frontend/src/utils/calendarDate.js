const RAIL_MONTHS = [
  "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
  "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
];

const RAIL_MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const RAIL_WEEKDAYS = [
  "SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY",
  "THURSDAY", "FRIDAY", "SATURDAY",
];

const ARABIC_RAIL_MONTHS = [
  "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
  "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
];

const ARABIC_RAIL_WEEKDAYS = [
  "الأحد", "الاثنين", "الثلاثاء", "الأربعاء",
  "الخميس", "الجمعة", "السبت",
];

export const formatRailCalendarDate = (date = new Date(), language = "en") => ({
  day: date.getDate(),
  month: language === "ar"
    ? ARABIC_RAIL_MONTHS[date.getMonth()]
    : RAIL_MONTHS[date.getMonth()],
  year: date.getFullYear(),
});

export const formatRailWeekday = (date = new Date(), language = "en") => (
  language === "ar"
    ? ARABIC_RAIL_WEEKDAYS[date.getDay()]
    : RAIL_WEEKDAYS[date.getDay()]
);

export const formatRailCalendarLabel = (date = new Date(), language = "en") => {
  if (language === "ar") {
    return `اليوم ${formatRailWeekday(date, language)}، ${date.getDate()} ${ARABIC_RAIL_MONTHS[date.getMonth()]} ${date.getFullYear()}.`;
  }

  const weekday = formatRailWeekday(date).toLowerCase();
  const readableWeekday = `${weekday.charAt(0).toUpperCase()}${weekday.slice(1)}`;
  return `Today is ${readableWeekday}, ${RAIL_MONTH_NAMES[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}.`;
};
