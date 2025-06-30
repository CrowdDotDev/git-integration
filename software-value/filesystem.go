package main

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
)

// findRepositoriesDirectories returns all immediate subdirectories within the given path, which contain a .git directory.
// This creates a list (repoDirs) with all the repositories' paths.
// At the time of writing, we have a little over 14K directories.
// It doesn't seem to be a problem for now, but we should keep this in mind in the future with more repositories.
func findRepositoriesDirectories(dirPath string) ([]string, error) {
	var repoDirs []string

	entries, err := os.ReadDir(dirPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read directory '%s': %w", dirPath, err)
	}

	for _, entry := range entries {
		if entry.IsDir() {
			subdirPath := filepath.Join(dirPath, entry.Name())
			gitDirPath := filepath.Join(subdirPath, ".git")
			if stat, err := os.Stat(gitDirPath); err == nil && stat.IsDir() {
				repoDirs = append(repoDirs, subdirPath)
			} else {
				log.Printf("Skipping directory '%s', it does not contain a .git directory.", subdirPath)
			}
		}
	}

	if len(repoDirs) == 0 {
		log.Printf("No git repositories found in %s", dirPath)
	}

	return repoDirs, nil
}

func getFileSizes(dirPath string) (map[string]int64, error) {
	fileSizes := make(map[string]int64)

	err := filepath.Walk(dirPath, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		if !info.IsDir() {
			fileSizes[path] = info.Size()
		}

		return nil
	})

	if err != nil {
		return nil, fmt.Errorf("failed to walk directory '%s': %w", dirPath, err)
	}

	return fileSizes, nil
}
