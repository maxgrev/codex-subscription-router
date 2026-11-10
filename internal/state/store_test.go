package state

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestStoreBootstrapsPrimaryAndPersistsThreadAffinity(t *testing.T) {
	root := t.TempDir()
	primaryHome := filepath.Join(root, "primary")
	store, err := Open(filepath.Join(root, "mux"), primaryHome)
	if err != nil {
		t.Fatal(err)
	}
	accounts := store.Accounts()
	if len(accounts) != 1 || accounts[0].ID != "primary" || !accounts[0].Controller {
		t.Fatalf("unexpected bootstrap accounts: %#v", accounts)
	}
	added, err := store.AddAccount("Work")
	if err != nil {
		t.Fatal(err)
	}
	config, err := os.ReadFile(filepath.Join(added.CodexHome, "config.toml"))
	if err != nil {
		t.Fatal(err)
	}
	wantConfig := "cli_auth_credentials_store = \"file\"\nmcp_oauth_credentials_store = \"file\"\n"
	if string(config) != wantConfig {
		t.Fatalf("unexpected isolated config: %q", config)
	}
	if err := store.SetThreadOwner("thread-1", added.ID); err != nil {
		t.Fatal(err)
	}

	reopened, err := Open(filepath.Join(root, "mux"), primaryHome)
	if err != nil {
		t.Fatal(err)
	}
	owner, ok := reopened.ThreadOwner("thread-1")
	if !ok || owner != added.ID {
		t.Fatalf("thread affinity was not persisted: owner=%q ok=%v", owner, ok)
	}
}

func TestAccountConfigInheritsManagedMCPAndPreservesLocalProjects(t *testing.T) {
	root := t.TempDir()
	primaryHome := filepath.Join(root, "primary")
	if err := os.MkdirAll(primaryHome, 0o700); err != nil {
		t.Fatal(err)
	}
	primaryConfig := `model = "gpt-test"

[mcp_servers.node_repl]
command = "/Applications/Codex++.app/node_repl"

[mcp_servers.node_repl.env]
SKY_CUA_SERVICE_PATH = "/Applications/Codex++ Computer Use.app"

[projects."/primary-only"]
trust_level = "trusted"
`
	if err := os.WriteFile(filepath.Join(primaryHome, "config.toml"), []byte(primaryConfig), 0o600); err != nil {
		t.Fatal(err)
	}

	muxRoot := filepath.Join(root, "mux")
	store, err := Open(muxRoot, primaryHome)
	if err != nil {
		t.Fatal(err)
	}
	added, err := store.AddAccount("Work")
	if err != nil {
		t.Fatal(err)
	}
	configPath := filepath.Join(added.CodexHome, "config.toml")
	config, err := os.ReadFile(configPath)
	if err != nil {
		t.Fatal(err)
	}
	text := string(config)
	for _, expected := range []string{
		`cli_auth_credentials_store = "file"`,
		`mcp_oauth_credentials_store = "file"`,
		`model = "gpt-test"`,
		`[mcp_servers.node_repl]`,
		`SKY_CUA_SERVICE_PATH = "/Applications/Codex++ Computer Use.app"`,
	} {
		if !strings.Contains(text, expected) {
			t.Fatalf("account config is missing %q:\n%s", expected, text)
		}
	}
	if strings.Contains(text, "/primary-only") {
		t.Fatalf("primary project trust leaked into account config:\n%s", text)
	}

	text += `
[projects."/account-project"]
trust_level = "trusted"
`
	if err := os.WriteFile(configPath, []byte(text), 0o600); err != nil {
		t.Fatal(err)
	}
	primaryConfig = strings.ReplaceAll(primaryConfig, "gpt-test", "gpt-updated")
	if err := os.WriteFile(filepath.Join(primaryHome, "config.toml"), []byte(primaryConfig), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := Open(muxRoot, primaryHome); err != nil {
		t.Fatal(err)
	}
	config, err = os.ReadFile(configPath)
	if err != nil {
		t.Fatal(err)
	}
	text = string(config)
	if !strings.Contains(text, `model = "gpt-updated"`) {
		t.Fatalf("managed config was not refreshed:\n%s", text)
	}
	if !strings.Contains(text, `[projects."/account-project"]`) {
		t.Fatalf("account project trust was not preserved:\n%s", text)
	}
}

func TestSyncManagedConfigPropagatesPluginsWithoutRestart(t *testing.T) {
	root := t.TempDir()
	primaryHome := filepath.Join(root, "primary")
	if err := os.MkdirAll(primaryHome, 0o700); err != nil {
		t.Fatal(err)
	}
	configPath := filepath.Join(primaryHome, "config.toml")
	if err := os.WriteFile(configPath, []byte("model = \"before\"\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	store, err := Open(filepath.Join(root, "mux"), primaryHome)
	if err != nil {
		t.Fatal(err)
	}
	account, err := store.AddAccount("Work")
	if err != nil {
		t.Fatal(err)
	}
	updated := "model = \"after\"\n\n[plugins.\"browser@openai-bundled\"]\nenabled = true\n"
	if err := os.WriteFile(configPath, []byte(updated), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := store.SyncManagedConfig(); err != nil {
		t.Fatal(err)
	}
	isolated, err := os.ReadFile(filepath.Join(account.CodexHome, "config.toml"))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(isolated), `[plugins."browser@openai-bundled"]`) {
		t.Fatalf("plugin config did not propagate:\n%s", isolated)
	}
}

func TestPreferredAccountPersistsAndClears(t *testing.T) {
	root := t.TempDir()
	store, err := Open(filepath.Join(root, "mux"), filepath.Join(root, "primary"))
	if err != nil {
		t.Fatal(err)
	}
	added, err := store.AddAccount("Work")
	if err != nil {
		t.Fatal(err)
	}
	if _, ok := store.PreferredAccount(); ok {
		t.Fatal("expected no preferred account by default")
	}
	if err := store.SetPreferredAccount(added.ID); err != nil {
		t.Fatal(err)
	}
	id, ok := store.PreferredAccount()
	if !ok || id != added.ID {
		t.Fatalf("preferred account was not stored: id=%q ok=%v", id, ok)
	}

	reopened, err := Open(filepath.Join(root, "mux"), filepath.Join(root, "primary"))
	if err != nil {
		t.Fatal(err)
	}
	id, ok = reopened.PreferredAccount()
	if !ok || id != added.ID {
		t.Fatalf("preferred account was not persisted: id=%q ok=%v", id, ok)
	}

	enabled := false
	if _, err := reopened.UpdateAccount(added.ID, nil, &enabled); err != nil {
		t.Fatal(err)
	}
	if _, ok := reopened.PreferredAccount(); ok {
		t.Fatal("disabling the preferred account should clear the selection")
	}
	if err := reopened.SetPreferredAccount("missing"); err == nil {
		t.Fatal("expected an error for an unknown account")
	}
	if err := reopened.SetPreferredAccount(""); err != nil {
		t.Fatal(err)
	}
}

func TestMaintainOfficialComputerUseConfigKeepsBothAppsOnTheirHelpers(t *testing.T) {
	root := t.TempDir()
	home := filepath.Join(root, "home")
	primaryHome := filepath.Join(home, ".codex")
	if err := os.MkdirAll(primaryHome, 0o700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("HOME", home)
	routerApp := filepath.Join(home, "Applications", "Codex++.app")
	routerHelper := filepath.Join(home, "Applications", "Codex++ Computer Use.app")
	officialHelper := filepath.Join(primaryHome, "computer-use", "Codex Computer Use.app")
	primaryConfig := `model = "gpt-test"

notify = ["` + routerHelper + `/Contents/SharedSupport/SkyComputerUseClient.app/Contents/MacOS/SkyComputerUseClient", "turn-ended"]

[mcp_servers.node_repl]
command = "` + routerApp + `/Contents/Resources/cua_node/bin/node_repl"

[mcp_servers.node_repl.env]
SKY_CUA_SERVICE_PATH = "` + routerHelper + `"
CODEX_CLI_PATH = "` + routerApp + `/Contents/Resources/codex"
`
	if err := os.WriteFile(filepath.Join(primaryHome, "config.toml"), []byte(primaryConfig), 0o600); err != nil {
		t.Fatal(err)
	}
	store, err := Open(filepath.Join(root, "mux"), primaryHome)
	if err != nil {
		t.Fatal(err)
	}
	isolated, err := store.AddAccount("Work")
	if err != nil {
		t.Fatal(err)
	}
	if err := store.MaintainOfficialComputerUseConfig(home); err != nil {
		t.Fatal(err)
	}
	primary := string(mustRead(t, filepath.Join(primaryHome, "config.toml")))
	if strings.Contains(primary, routerApp) || strings.Contains(primary, routerHelper) {
		t.Fatalf("shared config still points at the router:\n%s", primary)
	}
	if !strings.Contains(primary, `SKY_CUA_SERVICE_PATH = "`+officialHelper+`"`) {
		t.Fatalf("shared config did not restore the official helper:\n%s", primary)
	}
	isolatedText := string(mustRead(t, filepath.Join(isolated.CodexHome, "config.toml")))
	if strings.Contains(isolatedText, officialHelper) || strings.Contains(isolatedText, "/Applications/ChatGPT.app") {
		t.Fatalf("isolated config still points at official ChatGPT:\n%s", isolatedText)
	}
	if !strings.Contains(isolatedText, `SKY_CUA_SERVICE_PATH = "`+routerHelper+`"`) {
		t.Fatalf("isolated config did not keep the router helper:\n%s", isolatedText)
	}
}

func TestRestoreOfficialComputerUseConfigRewritesSharedHelperPaths(t *testing.T) {
	root := t.TempDir()
	home := filepath.Join(root, "home")
	primaryHome := filepath.Join(home, ".codex")
	if err := os.MkdirAll(primaryHome, 0o700); err != nil {
		t.Fatal(err)
	}
	routerApp := filepath.Join(home, "Applications", "Codex++.app")
	routerHelper := filepath.Join(home, "Applications", "Codex++ Computer Use.app")
	officialHelper := filepath.Join(primaryHome, "computer-use", "Codex Computer Use.app")
	nestedNotify := `notify = ["` + routerHelper + `/Contents/SharedSupport/SkyComputerUseClient.app/Contents/MacOS/SkyComputerUseClient", "turn-ended", "--previous-notify", "[\\\"nested\\\"]"]`
	primaryConfig := `model = "gpt-test"

` + nestedNotify + `

[mcp_servers.node_repl]
command = "` + routerApp + `/Contents/Resources/cua_node/bin/node_repl"

[mcp_servers.node_repl.env]
SKY_CUA_SERVICE_PATH = "` + routerHelper + `"
CODEX_CLI_PATH = "` + routerApp + `/Contents/Resources/codex"
`
	if err := os.WriteFile(filepath.Join(primaryHome, "config.toml"), []byte(primaryConfig), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := RestoreOfficialComputerUseConfig(primaryHome, home); err != nil {
		t.Fatal(err)
	}
	text := string(mustRead(t, filepath.Join(primaryHome, "config.toml")))
	if strings.Contains(text, routerApp) || strings.Contains(text, routerHelper) {
		t.Fatalf("shared config still points at the router:\n%s", text)
	}
	if strings.Contains(text, "--previous-notify") {
		t.Fatalf("nested notify hook was not reset:\n%s", text)
	}
	for _, expected := range []string{
		`command = "/Applications/ChatGPT.app/Contents/Resources/cua_node/bin/node_repl"`,
		`SKY_CUA_SERVICE_PATH = "` + officialHelper + `"`,
		`CODEX_CLI_PATH = "/Applications/ChatGPT.app/Contents/Resources/codex"`,
		`notify = ["` + officialHelper + `/Contents/SharedSupport/SkyComputerUseClient.app/Contents/MacOS/SkyComputerUseClient", "turn-ended"]`,
	} {
		if !strings.Contains(text, expected) {
			t.Fatalf("restored config is missing %q:\n%s", expected, text)
		}
	}
}

func TestRestoreOfficialComputerUseConfigRewritesLegacyRouterPaths(t *testing.T) {
	root := t.TempDir()
	home := filepath.Join(root, "home")
	primaryHome := filepath.Join(home, ".codex")
	if err := os.MkdirAll(primaryHome, 0o700); err != nil {
		t.Fatal(err)
	}
	legacyApp := filepath.Join(home, "Applications", "Codex Subscription Router.app")
	legacyHelper := filepath.Join(home, "Applications", "Codex Subscription Router Computer Use.app")
	officialHelper := filepath.Join(primaryHome, "computer-use", "Codex Computer Use.app")
	primaryConfig := `[mcp_servers.node_repl]
command = "` + legacyApp + `/Contents/Resources/cua_node/bin/node_repl"

[mcp_servers.node_repl.env]
SKY_CUA_SERVICE_PATH = "` + legacyHelper + `"
`
	if err := os.WriteFile(filepath.Join(primaryHome, "config.toml"), []byte(primaryConfig), 0o600); err != nil {
		t.Fatal(err)
	}
	needsRestore, err := OfficialComputerUseConfigNeedsRestore(primaryHome, home)
	if err != nil {
		t.Fatal(err)
	}
	if !needsRestore {
		t.Fatal("legacy router paths should need a restore")
	}
	if err := RestoreOfficialComputerUseConfig(primaryHome, home); err != nil {
		t.Fatal(err)
	}
	text := string(mustRead(t, filepath.Join(primaryHome, "config.toml")))
	for _, expected := range []string{
		`command = "/Applications/ChatGPT.app/Contents/Resources/cua_node/bin/node_repl"`,
		`SKY_CUA_SERVICE_PATH = "` + officialHelper + `"`,
	} {
		if !strings.Contains(text, expected) {
			t.Fatalf("restored config is missing %q:\n%s", expected, text)
		}
	}
}

func TestSyncIsolatedConfigRetargetsOfficialComputerUsePaths(t *testing.T) {
	root := t.TempDir()
	home := t.TempDir()
	t.Setenv("HOME", home)
	primaryHome := filepath.Join(root, "primary")
	isolatedHome := filepath.Join(root, "isolated")
	if err := os.MkdirAll(primaryHome, 0o700); err != nil {
		t.Fatal(err)
	}
	officialHelper := filepath.Join(primaryHome, "computer-use", "Codex Computer Use.app")
	routerHelper := filepath.Join(home, "Applications", "Codex++ Computer Use.app")
	primaryConfig := `model = "gpt-test"

notify = ["` + officialHelper + `/Contents/SharedSupport/SkyComputerUseClient.app/Contents/MacOS/SkyComputerUseClient", "turn-ended"]

[mcp_servers.node_repl.env]
SKY_CUA_SERVICE_PATH = "` + officialHelper + `"
CODEX_CLI_PATH = "/Applications/ChatGPT.app/Contents/Resources/codex"
`
	if err := os.WriteFile(filepath.Join(primaryHome, "config.toml"), []byte(primaryConfig), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := syncIsolatedConfig(primaryHome, isolatedHome); err != nil {
		t.Fatal(err)
	}
	text := string(mustRead(t, filepath.Join(isolatedHome, "config.toml")))
	if strings.Contains(text, officialHelper) || strings.Contains(text, "/Applications/ChatGPT.app") {
		t.Fatalf("isolated config still points at official ChatGPT:\n%s", text)
	}
	if !strings.Contains(text, `SKY_CUA_SERVICE_PATH = "`+routerHelper+`"`) {
		t.Fatalf("isolated config did not retarget Computer Use:\n%s", text)
	}
}

func mustRead(t *testing.T, path string) []byte {
	t.Helper()
	contents, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	return contents
}

func TestUpdateAccountPreservesController(t *testing.T) {
	root := t.TempDir()
	store, err := Open(root, filepath.Join(root, "primary"))
	if err != nil {
		t.Fatal(err)
	}
	label := "Personal"
	enabled := false
	account, err := store.UpdateAccount("primary", &label, &enabled)
	if err != nil {
		t.Fatal(err)
	}
	if account.Label != label || account.Enabled || !account.Controller {
		t.Fatalf("unexpected updated account: %#v", account)
	}
}
