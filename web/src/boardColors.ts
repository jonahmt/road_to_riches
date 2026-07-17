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

export const SUIT_COLORS: Readonly<Record<string, string>> = {
  SPADE: "#56cfff",
  HEART: "#ff6aae",
  DIAMOND: "#ffd84d",
  CLUB: "#74df67",
};

export const BOON_ICON_COLOR = "#ffb703";
export const BOOM_ICON_COLOR = "#f05a28";
export const TAKE_A_BREAK_ICON_COLOR = "#ffe8a3";
export const STOCKBROKER_ICON_COLOR = "#62d6a1";

export const UNOWNED_MINIMAP_SHOP_COLOR = "#70747d";

export function getMinimapShopColor(ownerId: number | null): string {
  return ownerId === null
    ? UNOWNED_MINIMAP_SHOP_COLOR
    : PLAYER_COLORS[ownerId % PLAYER_COLORS.length];
}
