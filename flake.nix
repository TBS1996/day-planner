{
  description = "Python curses desktop-notifier app";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
        };

        python-env = pkgs.python311.withPackages (ps: with ps; [
          dacite
          desktop-notifier
        ]);
      in {
        devShells.default = pkgs.mkShell {
          packages = [ python-env ];
          nativeBuildInputs = [ pkgs.ncurses ]; # <- Add this line!
        };
      });
}

