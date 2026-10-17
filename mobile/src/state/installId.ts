/**
 * This install's id for preview mode. The backend issues it (unguessable) on
 * the first preview; the app keeps it in the iOS Keychain, which survives
 * deleting and reinstalling the app — so a reinstall gets the same anonymous
 * account and not a second free AI log.
 */
import * as SecureStore from 'expo-secure-store';

const KEY = 'yy.install_id.v1';

/** The stored id, `null` if none yet; throws if the Keychain can't be read. */
export async function readInstallId(): Promise<string | null> {
  return SecureStore.getItemAsync(KEY);
}

export async function saveInstallId(id: string): Promise<void> {
  try {
    await SecureStore.setItemAsync(KEY, id);
  } catch {
    // Best-effort: without the Keychain this install simply gets a new id next time.
  }
}
