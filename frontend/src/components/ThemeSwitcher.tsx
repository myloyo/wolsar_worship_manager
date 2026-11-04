import { Button, Dropdown } from "antd";
import { CheckOutlined, BgColorsOutlined } from "@ant-design/icons";
import { useInterfaceTheme } from "../ThemeProvider";
import { isThemeId, palettes, themeIds } from "../themes";

export default function ThemeSwitcher() {
  const { id, setTheme } = useInterfaceTheme();
  return (
    <Dropdown
      trigger={["click"]}
      menu={{
        selectedKeys: [id],
        items: themeIds.map((key) => ({
          key,
          label: (
            <span className="theme-option">
              <i style={{ background: palettes[key].accent }} />
              {palettes[key].name}
              {id === key && <CheckOutlined />}
            </span>
          ),
        })),
        onClick: ({ key }) => {
          if (isThemeId(key)) setTheme(key);
        },
      }}
    >
      <Button
        type="text"
        className="theme-switcher"
        icon={<BgColorsOutlined />}
        aria-label="Сменить тему интерфейса"
        title="Сменить тему"
      >
        {palettes[id].name}
      </Button>
    </Dropdown>
  );
}
