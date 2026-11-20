#!/bin/bash

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command')

TOKENS=()
token=""
quote=""
escaped=false
has_token=false

for ((i = 0; i < ${#COMMAND}; i++)); do
  char="${COMMAND:i:1}"

  if [[ "$escaped" == true ]]; then
    token+="$char"
    escaped=false
    continue
  fi

  case "$quote" in
    "'")
      if [[ "$char" == "'" ]]; then quote=""; else token+="$char"; fi
      ;;
    '"')
      if [[ "$char" == "\\" ]]; then
        escaped=true
      elif [[ "$char" == '"' ]]; then
        quote=""
      else
        token+="$char"
      fi
      ;;
    *)
      case "$char" in
        "\\")
          escaped=true
          has_token=true
          ;;
        "'"|'"')
          quote="$char"
          has_token=true
          ;;
        [[:space:]])
          if [[ "$has_token" == true ]]; then
            TOKENS+=("$token")
            token=""
            has_token=false
          fi
          ;;
        [\;\&\|\(\)\<\>])
          if [[ "$has_token" == true ]]; then TOKENS+=("$token"); token=""; has_token=false; fi
          TOKENS+=("$char")
          ;;
        *)
          token+="$char"
          has_token=true
          ;;
      esac
      ;;
  esac
done

if [[ "$escaped" == true ]]; then token+="\\"; has_token=true; fi
if [[ "$has_token" == true ]]; then TOKENS+=("$token"); fi

for ((i = 0; i < ${#TOKENS[@]}; i++)); do
  [[ "${TOKENS[i]}" == "git" ]] || continue

  j=$((i + 1))
  while ((j < ${#TOKENS[@]})); do
    case "${TOKENS[j]}" in
      -C|-c|--git-dir|--work-tree|--namespace|--super-prefix|--config-env)
        j=$((j + 2))
        ;;
      --*=*|-*)
        j=$((j + 1))
        ;;
      *)
        break
        ;;
    esac
  done

  ((j < ${#TOKENS[@]})) || continue
  subcommand="${TOKENS[j]}"
  dangerous_pattern=""
  delete_branch=false
  force_branch=false

  case "$subcommand" in
    push)
      dangerous_pattern="git push"
      ;;
    reset)
      for ((k = j + 1; k < ${#TOKENS[@]}; k++)); do
        [[ "${TOKENS[k]}" == "--" ]] && break
        if [[ "${TOKENS[k]}" == "--hard" ]]; then dangerous_pattern="git reset --hard"; break; fi
      done
      ;;
    clean)
      for ((k = j + 1; k < ${#TOKENS[@]}; k++)); do
        [[ "${TOKENS[k]}" == "--" ]] && break
        if [[ "${TOKENS[k]}" == "--force" || "${TOKENS[k]}" =~ ^-[^-]*f ]]; then
          dangerous_pattern="git clean -f"
          break
        fi
      done
      ;;
    branch)
      for ((k = j + 1; k < ${#TOKENS[@]}; k++)); do
        [[ "${TOKENS[k]}" == "--" ]] && break
        if [[ "${TOKENS[k]}" == "--delete" ]]; then
          delete_branch=true
        elif [[ "${TOKENS[k]}" == "--force" ]]; then
          force_branch=true
        elif [[ "${TOKENS[k]}" =~ ^-[^-]*D ]]; then
          dangerous_pattern="git branch -D"
          break
        fi
      done
      if [[ "$delete_branch" == true && "$force_branch" == true ]]; then
        dangerous_pattern="git branch --delete --force"
      fi
      ;;
    checkout|restore)
      for ((k = j + 1; k < ${#TOKENS[@]}; k++)); do
        if [[ "${TOKENS[k]}" == "." ]]; then
          dangerous_pattern="git $subcommand ."
          break
        fi
      done
      ;;
  esac

  if [[ -n "$dangerous_pattern" ]]; then
    echo "BLOCKED: '$COMMAND' matches dangerous pattern '$dangerous_pattern'. The user has prevented you from doing this." >&2
    exit 2
  fi
done

exit 0
