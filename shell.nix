{ pkgs ? import <nixpkgs> { } }:

let
  include-path = "${pkgs.linuxHeaders}/include";
in

pkgs.mkShell {

  shellHook = ''
    runHook preShellHook

    # add headers for python package compile
    export C_INCLUDE_PATH="${include-path}"

    # enable poetry and enter virtual environment
    source $(poetry env info --path)/bin/activate
    poetry install --no-interaction --no-root

    runHook postShellHook
  '';

  buildInputs = with pkgs; [
    poetry

    alsa-lib

    autoconf
    automake
    bison
    flex
    fontforge
    gnumake
    gcc
    libiconv
    libtool # freetype calls glibtoolize
    linuxHeaders
    makeWrapper
    pkg-config
  ];
}
