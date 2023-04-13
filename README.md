<p align="left">
<img src="https://github.com/kreatolinux/logo/blob/master/withtext.png"> 
</p>

# Kreato Linux official package repository
This is the Kreato Linux package repository. 
You should find the required packages for a nice base system here.

# Usage
Run `kpkg update`. This should automatically clone the repository. If it does not, [please file a bug report](https://github.com/kreatolinux/src/issues).
If for some reason you need to clone it by hand, you can do so aswell.
```
mkdir -p /etc/kpkg/repos
git clone https://github.com/kreatolinux/kpkg-repo.git --depth=1 /etc/kpkg/repos/main
```

# Development
Every package exists in a seperate directory.

* For runfiles, check out kpkg_run(8)
* Dependencies go onto the `deps` file. Each dependency should go onto a seperate line.
* Build dependencies go onto the `build_deps` file. Each dependency should go onto a seperate line.

# Credits
* Arch Linux packages
* Linux From Scratch packages
* KISS Linux packages.

Please note that this does not mean that the packages are taken from these projects, it just means that the packages have inspirations from these projects' packages aswell. Check for the packages' runfile for details.

# License
Unless explicitly stated, this repository is licensed under GNU Affero General Public License version 3 or later (if prefered).

This project is a part of Kreato Linux.

nyaa-repo is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

nyaa-repo is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with Kreato Linux.  If not, see <https://www.gnu.org/licenses/>.
