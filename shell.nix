{ pkgs ? import <nixpkgs> { } }:
pkgs.mkShell {

  shellHook = ''
    runHook preShellHook

    # add headers for python package compile
    export C_INCLUDE_PATH="${pkgs.linuxHeaders}/include"

    # for ALSA to find plugins
    export ALSA_PLUGIN_DIR="${pkgs.alsa-plugins}/lib/alsa-lib/"

    # enable poetry and enter virtual environment
    poetry install --no-interaction --no-root
    source $(poetry env info --path)/bin/activate

    runHook postShellHook
  '';

  buildInputs = with pkgs; [
    poetry

    alsa-lib
    alsa-plugins

    gnumake
    gcc
    linuxHeaders
  ];
}
