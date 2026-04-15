export interface ConnectorSyncResult {
  importedTransactions: number;
  updatedPrices: number;
  message: string;
}

export interface Connector {
  syncAccount(accountId: string, creds?: unknown): Promise<ConnectorSyncResult>;
}
