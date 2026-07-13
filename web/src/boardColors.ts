export const PLAYER_COLORS = [
  "#54d6ff",
  "#ff7ab6",
  "#ffd166",
  "#77dd77",
  "#c792ea",
  "#ff9f1c",
] as const;

export const DISTRICT_COLORS = [
  "#54d6ff",
  "#ff7ab6",
  "#ffd166",
  "#77dd77",
  "#c792ea",
  "#ff9f1c",
] as const;

export const DISTRICT_BORDER_COLORS = [
  "#1677a8",
  "#c63f84",
  "#b58416",
  "#248b59",
  "#7952b3",
  "#c66313",
] as const;

export const UNOWNED_MINIMAP_SHOP_COLOR = "#70747d";

export function getMinimapShopColor(ownerId: number | null): string {
  return ownerId === null
    ? UNOWNED_MINIMAP_SHOP_COLOR
    : PLAYER_COLORS[ownerId % PLAYER_COLORS.length];
}
