import { db } from "@/lib/db";
import { BaseCurrency } from "@/lib/types";

export const convertAmount = (
  amount: number,
  fromCurrency: string,
  toCurrency: BaseCurrency
) => {
  if (fromCurrency === toCurrency) {
    return amount;
  }

  const rates = db.getFxRates();
  const direct = rates.find(
    (item) =>
      item.baseCurrency.toUpperCase() === fromCurrency.toUpperCase() &&
      item.quoteCurrency.toUpperCase() === toCurrency.toUpperCase()
  );

  if (direct) {
    return amount * direct.rate;
  }

  const inverse = rates.find(
    (item) =>
      item.baseCurrency.toUpperCase() === toCurrency.toUpperCase() &&
      item.quoteCurrency.toUpperCase() === fromCurrency.toUpperCase()
  );

  if (inverse) {
    return amount / inverse.rate;
  }

  return amount;
};

export const getFxOverview = () => db.getFxRates();
