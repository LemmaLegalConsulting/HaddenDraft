export function factRecommendationState(response, fallbackSession = null) {
  const session = response?.session || fallbackSession;
  return {
    session,
    matter: response?.case || session?.matter || null,
    factIds: response?.factIds || session?.selectedFactIds || [],
    facts: response?.facts || response?.case?.facts || [],
  };
}

export function mergeFactIds(currentIds = [], nextIds = []) {
  return [...new Set([...currentIds, ...nextIds])];
}
