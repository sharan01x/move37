#!/bin/zsh

# Script to upgrade the local installation with the latest version from origin/master

# Fetch the latest changes from the remote repository
git fetch origin

# Reset the local master branch to match origin/master, overwriting any local changes
git reset --hard origin/master

# Remove untracked files and directories
# Use -d to remove directories in addition to files
# Use -f to force the removal (required if git configuration clean.requireForce is not set to false)
git clean -fd

echo "Upgrade complete. Your local repository is now synchronized with origin/master."
