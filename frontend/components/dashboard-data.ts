/** Métadonnées de présentation ; aucune valeur analytique n'est stockée côté client. */
export const serviceLabels: Record<string, string> = {
  URG: "Urgences",
  MED: "Médecine",
  REA: "Réanimation",
  CHI: "Chirurgie",
};

export const serviceColors: Record<string, string> = {
  URG: "#ef6b5d",
  MED: "#2c7a7b",
  REA: "#6054d8",
  CHI: "#d6942e",
};

export const fmt = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 });
