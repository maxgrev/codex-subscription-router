package state

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

const isolatedCredentialConfig = `cli_auth_credentials_store = "file"
mcp_oauth_credentials_store = "file"`

const (
	officialDesktopApp = "/Applications/ChatGPT.app"
	routerDesktopName  = "Codex++.app"
	routerHelperName   = "Codex++ Computer Use.app"
	officialHelperName = "Codex Computer Use.app"
	// Names from before the Codex++ rename, still possible in shared configs.
	legacyRouterDesktopName = "Codex Subscription Router.app"
	legacyRouterHelperName  = "Codex Subscription Router Computer Use.app"
)

var notifyLinePattern = regexp.MustCompile(`(?m)^notify = \[.*\]\s*$`)

// syncIsolatedConfig shares desktop-managed settings and MCP servers with an
// isolated subscription while keeping its credentials and project trust local.
func syncIsolatedConfig(primaryCodexHome, isolatedCodexHome string) error {
	if isolatedCodexHome == "" {
		return errors.New("isolated Codex home is required")
	}
	if err := os.MkdirAll(isolatedCodexHome, 0o700); err != nil {
		return fmt.Errorf("create isolated Codex home: %w", err)
	}
	if err := os.Chmod(isolatedCodexHome, 0o700); err != nil {
		return fmt.Errorf("secure isolated Codex home: %w", err)
	}

	primaryConfig, err := readConfig(filepath.Join(primaryCodexHome, "config.toml"))
	if err != nil {
		return fmt.Errorf("read primary config: %w", err)
	}
	configPath := filepath.Join(isolatedCodexHome, "config.toml")
	isolatedConfig, err := readConfig(configPath)
	if err != nil {
		return fmt.Errorf("read isolated config: %w", err)
	}

	managed := filterConfig(primaryConfig, func(section string) bool {
		return !isProjectSection(section)
	})
	managed = removeTopLevelCredentialSettings(managed)
	if home, homeErr := os.UserHomeDir(); homeErr == nil {
		managed = applyRouterComputerUsePaths(managed, primaryCodexHome, home)
	}
	projects := filterConfig(isolatedConfig, isProjectSection)

	parts := []string{isolatedCredentialConfig}
	if managed = strings.TrimSpace(managed); managed != "" {
		parts = append(parts, managed)
	}
	if projects = strings.TrimSpace(projects); projects != "" {
		parts = append(parts, projects)
	}
	return writeConfig(configPath, []byte(strings.Join(parts, "\n\n")+"\n"))
}

// RestoreOfficialComputerUseConfig rewrites router Computer Use paths in the
// shared primary config back to official ChatGPT. The primary account uses
// ~/.codex, so leaving SKY_CUA_SERVICE_PATH pointed at the independently
// signed helper makes official ChatGPT talk to a helper that rejects it.
func RestoreOfficialComputerUseConfig(primaryCodexHome, home string) error {
	_, err := restoreOfficialComputerUseConfig(primaryCodexHome, home)
	return err
}

func OfficialComputerUseConfigNeedsRestore(primaryCodexHome, home string) (bool, error) {
	contents, err := officialComputerUseConfig(primaryCodexHome)
	if err != nil || len(contents) == 0 {
		return false, err
	}
	updated := applyOfficialComputerUsePaths(string(contents), primaryCodexHome, home)
	return updated != string(contents), nil
}

func restoreOfficialComputerUseConfig(primaryCodexHome, home string) (bool, error) {
	contents, err := officialComputerUseConfig(primaryCodexHome)
	if err != nil {
		return false, err
	}
	if len(contents) == 0 {
		return false, nil
	}
	updated := applyOfficialComputerUsePaths(string(contents), primaryCodexHome, home)
	if updated == string(contents) {
		return false, nil
	}
	if err := writeConfig(filepath.Join(primaryCodexHome, "config.toml"), []byte(updated)); err != nil {
		return false, err
	}
	return true, nil
}

func officialComputerUseConfig(primaryCodexHome string) ([]byte, error) {
	if primaryCodexHome == "" {
		return nil, errors.New("primary Codex home is required")
	}
	contents, err := readConfig(filepath.Join(primaryCodexHome, "config.toml"))
	if err != nil {
		return nil, fmt.Errorf("read primary config: %w", err)
	}
	return contents, nil
}

func applyOfficialComputerUsePaths(contents, primaryCodexHome, home string) string {
	applications := filepath.Join(home, "Applications")
	officialHelper := officialComputerUseApp(primaryCodexHome)
	for _, router := range []struct{ app, helper string }{
		{routerDesktopName, routerHelperName},
		{legacyRouterDesktopName, legacyRouterHelperName},
	} {
		contents = retargetComputerUsePaths(
			contents,
			filepath.Join(applications, router.app),
			filepath.Join(applications, router.helper),
			officialDesktopApp,
			officialHelper,
		)
	}
	return rewriteNotifyLine(contents, officialHelper)
}

func applyRouterComputerUsePaths(contents, primaryCodexHome, home string) string {
	updated := retargetComputerUsePaths(
		contents,
		officialDesktopApp,
		officialComputerUseApp(primaryCodexHome),
		routerDesktopApp(home),
		routerComputerUseApp(home),
	)
	return rewriteNotifyLine(updated, routerComputerUseApp(home))
}

func retargetComputerUsePaths(contents, fromApp, fromHelper, toApp, toHelper string) string {
	if fromHelper != "" && toHelper != "" {
		contents = strings.ReplaceAll(contents, fromHelper, toHelper)
	}
	if fromApp != "" && toApp != "" {
		contents = strings.ReplaceAll(contents, fromApp, toApp)
	}
	return contents
}

func rewriteNotifyLine(contents, helperApp string) string {
	match := notifyLinePattern.FindString(contents)
	if match == "" {
		return contents
	}
	if !strings.Contains(match, "SkyComputerUseClient") &&
		!strings.Contains(match, "--previous-notify") &&
		!strings.Contains(match, routerHelperName) &&
		!strings.Contains(match, officialHelperName) {
		return contents
	}
	client := filepath.Join(
		helperApp,
		"Contents",
		"SharedSupport",
		"SkyComputerUseClient.app",
		"Contents",
		"MacOS",
		"SkyComputerUseClient",
	)
	return notifyLinePattern.ReplaceAllString(
		contents,
		fmt.Sprintf("notify = [%q, \"turn-ended\"]", client),
	)
}

func routerDesktopApp(home string) string {
	return filepath.Join(home, "Applications", routerDesktopName)
}

func routerComputerUseApp(home string) string {
	return filepath.Join(home, "Applications", routerHelperName)
}

func officialComputerUseApp(primaryCodexHome string) string {
	return filepath.Join(primaryCodexHome, "computer-use", officialHelperName)
}

func writeConfig(path string, contents []byte) error {
	temporaryPath := path + ".tmp"
	if err := os.WriteFile(temporaryPath, contents, 0o600); err != nil {
		return fmt.Errorf("write temporary config: %w", err)
	}
	if err := os.Chmod(temporaryPath, 0o600); err != nil {
		return fmt.Errorf("secure temporary config: %w", err)
	}
	if err := os.Rename(temporaryPath, path); err != nil {
		return fmt.Errorf("commit config: %w", err)
	}
	return nil
}

func readConfig(path string) ([]byte, error) {
	contents, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	return contents, err
}

func filterConfig(contents []byte, keep func(section string) bool) string {
	var builder strings.Builder
	section := ""
	for _, line := range strings.Split(string(contents), "\n") {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "[") && strings.HasSuffix(trimmed, "]") {
			section = strings.TrimSpace(strings.TrimSuffix(strings.TrimPrefix(trimmed, "["), "]"))
		}
		if keep(section) {
			builder.WriteString(line)
			builder.WriteByte('\n')
		}
	}
	return builder.String()
}

func removeTopLevelCredentialSettings(contents string) string {
	var builder strings.Builder
	section := ""
	for _, line := range strings.Split(contents, "\n") {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "[") && strings.HasSuffix(trimmed, "]") {
			section = strings.TrimSpace(strings.TrimSuffix(strings.TrimPrefix(trimmed, "["), "]"))
		}
		if section == "" && (strings.HasPrefix(trimmed, "cli_auth_credentials_store =") ||
			strings.HasPrefix(trimmed, "mcp_oauth_credentials_store =")) {
			continue
		}
		builder.WriteString(line)
		builder.WriteByte('\n')
	}
	return builder.String()
}

func isProjectSection(section string) bool {
	return section == "projects" || strings.HasPrefix(section, "projects.")
}

func samePath(left, right string) bool {
	if left == "" || right == "" {
		return false
	}
	leftAbsolute, leftErr := filepath.Abs(left)
	rightAbsolute, rightErr := filepath.Abs(right)
	if leftErr != nil || rightErr != nil {
		return filepath.Clean(left) == filepath.Clean(right)
	}
	return filepath.Clean(leftAbsolute) == filepath.Clean(rightAbsolute)
}
