
import { expect, test } from "@playwright/test";

test("affiche les huit vues et les filtres sans lancer de calcul", async ({ page }) => {
  const writeRequests: string[] = [];

  page.on("request", (request) => {
    if (request.method() !== "GET") {
      writeRequests.push(`${request.method()} ${request.url()}`);
    }
  });

  await page.goto("/");

  // Vérification de la vue d'ensemble
  await expect(
    page.getByRole("heading", { name: "Vue d’ensemble", exact: true })
  ).toBeVisible();

  await expect(
    page.getByText("Données synthétiques uniquement")
  ).toBeVisible();

  // Vérification des huit vues du dashboard
  const views = [
    ["Exploration des données", "Exploration des données"],
    ["Prévisions", "Prévisions"],
    ["Allocation", "Allocation des ressources"],
    ["Méthodes", "Comparaison des méthodes"],
    ["Scénarios", "Scénarios"],
    ["Sensibilité", "Analyse de sensibilité"],
    ["Expériences & export", "Expériences et export"],
  ] as const;

  for (const [label, heading] of views) {
    await page.getByRole("button", { name: label, exact: true }).click();

    await expect(
      page.getByRole("heading", { name: heading, exact: true })
    ).toBeVisible();
  }

  // Vérification du filtre de service
  await page.getByRole("button", { name: "Sensibilité", exact: true }).click();

  await expect(
    page.getByRole("heading", {
      name: "Analyse de sensibilité",
      exact: true,
    })
  ).toBeVisible();

  const serviceFilter = page.getByLabel("Service");
  const serviceOptions = await serviceFilter.locator("option").evaluateAll(
    (options) => options.map((option) => {
      const element = option as HTMLOptionElement;
      return { value: element.value, text: element.textContent };
    }),
  );

  if (await serviceFilter.isDisabled()) {
    expect(serviceOptions).toEqual([{ value: "", text: "Indisponible" }]);
  } else {
    expect(serviceOptions.length).toBeGreaterThan(0);
    await serviceFilter.selectOption(serviceOptions[0].value);
  }

  await expect(
    page.getByRole("heading", {
      name: "Analyse de sensibilité",
      exact: true,
    })
  ).toBeVisible();

  // Vérification qu'aucun calcul n'a été lancé automatiquement
  expect(writeRequests).toEqual([]);
});
