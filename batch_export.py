#! /usr/bin/env python

from concurrent.futures import ThreadPoolExecutor
import inkex
import os
import subprocess
import tempfile
import copy
import logging
from collections import deque


class Options:
    def __init__(self, batch_exporter):
        self.current_file = batch_exporter.options.input_file

        # Export file page
        self.export_type = batch_exporter.options.export_type
        self.export_plain_svg = self._str_to_bool(
            batch_exporter.options.export_plain_svg
        )
        self.export_pdf_version = batch_exporter.options.export_pdf_version
        self.output_path = os.path.normpath(batch_exporter.options.path)
        self.overwrite_files = self._str_to_bool(batch_exporter.options.overwrite_files)
        self.export_manifest = self._str_to_bool(batch_exporter.options.export_manifest)

        # Controls page
        self.using_clones = self._str_to_bool(batch_exporter.options.using_clones)
        self.skip_hidden_layers = self._str_to_bool(
            batch_exporter.options.skip_hidden_layers
        )
        self.skip_prefix = batch_exporter.options.skip_prefix

        # Export size page
        self.export_area_type = batch_exporter.options.export_area_type
        self.export_area_size = batch_exporter.options.export_area_size
        self.export_res_type = batch_exporter.options.export_res_type
        self.export_res_dpi = batch_exporter.options.export_res_dpi
        self.export_res_width = batch_exporter.options.export_res_width
        self.export_res_height = batch_exporter.options.export_res_height

        # File naming page
        self.hierarchy_separator = batch_exporter.options.hierarchy_separator
        self.name_template = batch_exporter.options.name_template
        self.number_start = batch_exporter.options.number_start

        # Threads page
        self.number_threads = batch_exporter.options.number_threads
        self.chunks_size = batch_exporter.options.chunks_size

        # Help page
        self.use_logging = self._str_to_bool(batch_exporter.options.use_logging)
        if self.use_logging:
            self.log_path = os.path.expanduser(batch_exporter.options.log_path)
            self.overwrite_log = self._str_to_bool(batch_exporter.options.overwrite_log)
            log_file_name = os.path.join(self.log_path, "batch_export.log")
            if self.overwrite_log and os.path.exists(log_file_name):
                logging.basicConfig(
                    filename=log_file_name, filemode="w", level=logging.DEBUG
                )
            else:
                logging.basicConfig(filename=log_file_name, level=logging.DEBUG)

    def __str__(self):
        print = "===> EXTENSION PARAMETERS\n"
        print += "Current file: {}\n".format(self.current_file)
        print += "\n======> Export file page\n"
        print += "Export type: {}\n".format(self.export_type)
        print += "Export plain SVG: {}\n".format(self.export_plain_svg)
        print += "Export PDF version: {}\n".format(self.export_pdf_version)
        print += "Path: {}\n".format(self.output_path)
        print += "Overwrite files: {}\n".format(self.overwrite_files)
        print += "Export manifest JSON: {}\n".format(self.export_manifest)
        print += "\n======> Controls page\n"
        print += "Using clones: {}\n".format(self.using_clones)
        print += "Skip hidden layers: {}\n".format(self.skip_hidden_layers)
        print += "Skip prefix: {}\n".format(self.skip_prefix)
        print += "\n======> Export size page\n"
        print += "Export area type: {}\n".format(self.export_area_type)
        print += "Export area size: {}\n".format(self.export_area_size)
        print += "Export res type: {}\n".format(self.export_res_type)
        print += "Export res DPI: {}\n".format(self.export_res_dpi)
        print += "Export res width: {}\n".format(self.export_res_width)
        print += "Export res height: {}\n".format(self.export_res_height)
        print += "\n======> File naming page\n"
        print += "Hierarchy separator: {}\n".format(self.hierarchy_separator)
        print += "Name template: {}\n".format(self.name_template)
        print += "Start count at: {}\n".format(self.number_start)
        print += "\n======> Threads page\n"
        print += "Number threads: {}\n".format(self.number_threads)
        print += "Chunks size: {}\n".format(self.chunks_size)
        print += "\n======> Help page\n"
        print += "Use logging: {}\n".format(self.use_logging)
        print += "Overwrite log: {}\n".format(self.overwrite_log)
        print += "Log path: {}\n".format(self.log_path)
        print += "---------------------------------------\n"
        return print

    def _str_to_bool(self, str):
        if str.lower() == "true":
            return True
        return False


class BatchExporter(inkex.Effect):
    def __init__(self):
        """init the effetc library and get options from gui"""
        inkex.Effect.__init__(self)

        # Export file page
        self.arg_parser.add_argument(
            "--export-type",
            action="store",
            type=str,
            dest="export_type",
            default="svg",
            help="",
        )
        self.arg_parser.add_argument(
            "--export-plain-svg",
            action="store",
            type=str,
            dest="export_plain_svg",
            default=False,
            help="",
        )
        self.arg_parser.add_argument(
            "--export-pdf-version",
            action="store",
            type=str,
            dest="export_pdf_version",
            default="1.5",
            help="",
        )
        self.arg_parser.add_argument(
            "--path",
            action="store",
            type=str,
            dest="path",
            default="",
            help="export path",
        )
        self.arg_parser.add_argument(
            "--overwrite-files",
            action="store",
            type=str,
            dest="overwrite_files",
            default=False,
            help="",
        )
        self.arg_parser.add_argument(
            "--export-manifest",
            action="store",
            type=str,
            dest="export_manifest",
            default=True,
            help="",
        )

        # Controls page
        self.arg_parser.add_argument(
            "--using-clones",
            action="store",
            type=str,
            dest="using_clones",
            default=True,
            help="",
        )
        self.arg_parser.add_argument(
            "--skip-hidden-layers",
            action="store",
            type=str,
            dest="skip_hidden_layers",
            default=False,
            help="",
        )
        self.arg_parser.add_argument(
            "--skip-prefix",
            action="store",
            type=str,
            dest="skip_prefix",
            default="_",
            help="",
        )

        # TODO add prefix ignore layer

        # Export size page
        self.arg_parser.add_argument(
            "--export-area-type",
            action="store",
            type=str,
            dest="export_area_type",
            default="page",
            help="",
        )
        self.arg_parser.add_argument(
            "--export-area-size",
            action="store",
            type=str,
            dest="export_area_size",
            default="0:0:100:100",
            help="",
        )
        self.arg_parser.add_argument(
            "--export-res-type",
            action="store",
            type=str,
            dest="export_res_type",
            default="default",
            help="",
        )
        self.arg_parser.add_argument(
            "--export-res-dpi",
            action="store",
            type=int,
            dest="export_res_dpi",
            default="96",
            help="",
        )
        self.arg_parser.add_argument(
            "--export-res-width",
            action="store",
            type=int,
            dest="export_res_width",
            default="100",
            help="",
        )
        self.arg_parser.add_argument(
            "--export-res-height",
            action="store",
            type=int,
            dest="export_res_height",
            default="100",
            help="",
        )

        # File naming page
        self.arg_parser.add_argument(
            "--name-template",
            action="store",
            type=str,
            dest="name_template",
            default="[LAYER_NAME]",
            help="",
        )
        self.arg_parser.add_argument(
            "--number-start",
            action="store",
            type=int,
            dest="number_start",
            default="0",
            help="",
        )
        self.arg_parser.add_argument(
            "--hierarchy-separator",
            action="store",
            type=str,
            dest="hierarchy_separator",
            default="_",
            help="",
        )

        # Theads page
        self.arg_parser.add_argument(
            "--number-threads",
            action="store",
            type=int,
            dest="number_threads",
            default="4",
            help="",
        )
        self.arg_parser.add_argument(
            "--chunks-size",
            action="store",
            type=int,
            dest="chunks_size",
            default="1",
            help="",
        )

        # Help page
        self.arg_parser.add_argument(
            "--use-logging",
            action="store",
            type=str,
            dest="use_logging",
            default=False,
            help="",
        )
        self.arg_parser.add_argument(
            "--overwrite-log",
            action="store",
            type=str,
            dest="overwrite_log",
            default=False,
            help="",
        )
        self.arg_parser.add_argument(
            "--log-path", action="store", type=str, dest="log_path", default="", help=""
        )

        # HACK - the script is called with a "--tab controls" option as an argument from the notebook param in the inx file.
        # This argument is not used in the script. It's purpose is to suppress an error when the script is called.
        self.arg_parser.add_argument(
            "--tab", action="store", type=str, dest="tab", default="controls", help=""
        )

    def _debug_svg_doc_wait(self, doc):
        # Can't use delete=True, delete_on_close=False, since Inkscape use python 2.7
        with tempfile.NamedTemporaryFile(delete=False, suffix=".svg") as temporary_file:
            doc.write(temporary_file.name)
            temporary_file.close()

            logging.debug("    Debug temp file {}".format(temporary_file.name))

            with subprocess.Popen(
                ["start", "/WAIT", temporary_file.name], shell=True
            ) as proc:
                proc.wait()

            os.remove(temporary_file.name)

    def effect(self):
        # Check user options
        options = Options(self)
        logging.debug(options)

        # Is working on self.document is safe ? Security
        self.working_doc = copy.deepcopy(self.document)

        # Build the partial inkscape export command
        command = self.build_partial_command(options)

        # Replace or delete clones
        self.handles_clones(options.using_clones)

        # Delete skip branches
        self.delete_skipped_layers(options.skip_hidden_layers, options.skip_prefix)

        # Get the layers selected
        layers = self.get_layers()

        doc = self.create_base_export_document()

        with ThreadPoolExecutor(max_workers=options.number_threads) as executor:
            files_result = list(
                executor.map(
                    self.construct_thread(doc, command, options.use_logging),
                    layers,
                    chunksize=options.chunks_size,
                )
            )
            
        # TODO with Json returned to merge ?

        # TODO Json manifest

        """
        # For each layer export a file
        for layer_id, layer_label, layer_type, parents in layers:
            if layer_type == "fixed":
                continue

            show_layer_ids = [
                layer[0]
                for layer in layers
                if layer[2] == "fixed" or layer[0] == layer_id
            ]

            # Create the output folder if it doesn't exist
            if not os.path.exists(os.path.join(options.output_path)):
                os.makedirs(os.path.join(options.output_path))

            # Construct the name of the exported file
            if options.naming_scheme == "simple":
                file_name = self.get_simple_name(
                    options.use_number_prefix, counter, layer_label
                )
            else:
                file_name = self.get_advanced_name(
                    options.name_template, counter, layer_label
                )
            file_name = "{}.{}".format(file_name, options.export_type)
            logging.debug("  File name: {}".format(file_name))

            # Check if the file exists. If not, export it.
            destination_path = os.path.join(options.output_path, file_name)
            if not options.overwrite_files and os.path.exists(destination_path):
                logging.debug("  File already exists: {}\n".format(file_name))
                # TODO: Should this be the expected functionality of this scenario?
                counter += 1
                continue

            # Create a new file in which we delete unwanted layers to keep the exported file size to a minimum
            logging.debug("  Preparing layer [{}]".format(layer_label))
            temporary_file_path = self.manage_layers(
                layer_id,
                show_layer_ids,
                options.hierarchical_layers,
                options.using_clones,
            )

            # Export to file
            logging.debug("  Exporting [{}] as {}".format(layer_label, file_name))
            self.export_to_file(
                command.copy(),
                temporary_file_path,
                destination_path,
                options.use_logging,
            )

            # Clean up - delete the temporary file we have created
            os.remove(temporary_file_path)

            counter += 1
        """

    def handles_clones(self, using_clones):
        doc = self.working_doc
        svg_clones = doc.xpath("//svg:use[@xlink:href]", namespaces=inkex.NSS)

        clones_to_replace = {}

        # Search clones
        for clone in svg_clones:
            clone_id = clone.attrib["id"]
            # Find id ref and remove #
            ref_attrib_name = "{%s}href" % clone.nsmap["xlink"]
            clone_ref_id = clone.attrib[ref_attrib_name][1:]

            parent = clone.getparent()
            index = list(parent).index(clone)

            # Case multiple clones with same original
            if clone_ref_id not in clones_to_replace.keys():
                clones_to_replace[clone_ref_id] = []

            logging.debug("  Clone: [{}, {}, {}]".format(clone_id, clone_ref_id, index))
            clones_to_replace[clone_ref_id].append((parent, index, clone, clone_id))

        if using_clones:
            self.replace_clones_by_original(clones_to_replace)
        else:
            # Delete them to avoid corrupted file
            for clone_list in reversed(clones_to_replace.values()):
                for clone_infos in clone_list:
                    clone_infos[0].remove(clone_infos[2])

        # self._debug_svg_doc_wait(doc)
        logging.debug("  TOTAL NUMBER OF CLONES: {}\n".format(len(svg_clones)))

    def replace_clones_by_original(self, clones_to_replace):
        doc = self.working_doc
        for element in doc.iter():
            if "id" not in element.attrib:
                continue

            id = element.attrib["id"]
            if id in clones_to_replace.keys():
                for clone_infos in clones_to_replace[id]:
                    # Replace clone in parent by copy of original
                    copy_el = copy.deepcopy(element)
                    if "transform" in clone_infos[2].attrib:
                        copy_el.attrib["transform"] = clone_infos[2].attrib["transform"]

                    clone_infos[0].remove(clone_infos[2])
                    clone_infos[0].insert(clone_infos[1], copy_el)
                    logging.debug("  REPLACE: {}->{}".format(clone_infos[3], id))
                # Avoid re-apply replace with replaced element
                del clones_to_replace[id]

        # self._debug_svg_doc_wait(doc)

    def delete_skipped_layers(self, skip_hidden_layers, skip_prefix):
        doc = self.working_doc

        svg_layers = doc.xpath(
            '//svg:g[@inkscape:groupmode="layer"]', namespaces=inkex.NSS
        )
        layers_skipped = deque()

        for layer in svg_layers:
            label_attrib_name = "{%s}label" % layer.nsmap["inkscape"]
            if label_attrib_name not in layer.attrib:
                continue

            parent = layer.getparent()

            layer_id = layer.attrib["id"]
            layer_label: str = layer.attrib[label_attrib_name]

            # Delete hidden layers
            if layer_label.startswith(skip_prefix) or (
                skip_hidden_layers
                and "style" in layer.attrib
                and "display:none" in layer.attrib["style"]
            ):

                logging.debug("  Skip: [{}]".format(layer.attrib[label_attrib_name]))
                layers_skipped.appendleft([parent, layer])

        logging.debug(
            "  TOTAL NUMBER OF LAYERS SKIPPED: {}\n".format(len(layers_skipped))
        )

        # Delete children before parent
        for layer_info in reversed(layers_skipped):
            layer_info[0].remove(layer_info[1])

        # self._debug_svg_doc_wait(doc)

    def get_layers(self):
        svg_layers = self.working_doc.xpath(
            '//svg:g[@inkscape:groupmode="layer"]', namespaces=inkex.NSS
        )

        layers = []

        for layer in svg_layers:
            label_attrib_name = "{%s}label" % layer.nsmap["inkscape"]
            if label_attrib_name not in layer.attrib:
                continue

            # Get layer parents, if any
            parents = []
            parent = layer.getparent()
            while True:
                if label_attrib_name not in parent.attrib:
                    break
                # Found a parent layer
                # logging.debug("parent: {}".format(parent.attrib["id"]))
                parents.append(parent.attrib["id"])
                parent = parent.getparent()

            layer_id = layer.attrib["id"]
            layer_label = layer.attrib[label_attrib_name]
            layer_type = "export"

            logging.debug("  Use: [{}, {}]".format(layer_label, layer_type))
            layer_info = (layer, parents)  # filename ?
            layers.append([layer_id, layer_label, layer_type, parents, layer])

        logging.debug("  TOTAL NUMBER OF LAYERS: {}\n".format(len(layers)))
        logging.debug(layers)

        # self._debug_svg_doc_wait(doc)
        return layers

    def fill_and_check_paths(self, layer_infos, number_start):

        # TODO Test duplicate names/path
        logging.error("User error ?")
        messagebox.showerror(title="User error", message="Test")
        logging.error("User error 2 ?")

        return []

    def create_base_export_document(self):
        doc = copy.deepcopy(self.working_doc)

        to_delete = []

        # Remove all elements with a name (make a white document with options)
        for element in doc.getroot().getchildren():
            label_attrib_name = "{%s}label" % element.nsmap["inkscape"]
            if label_attrib_name not in element.attrib:
                continue
            to_delete.append(element)

        for element in to_delete:
            doc.getroot().remove(element)

        return doc

    def build_partial_command(self, options):
        command = ["inkscape", "--vacuum-defs"]

        if options.export_type == "svg" and options.export_plain_svg == True:
            command.append("--export-plain-svg")
        if options.export_type == "pdf":
            command.append("--export-pdf-version={}".format(options.export_pdf_version))

        # Export area - default: export area page
        if options.export_area_type == "drawing":
            command.append("--export-area-drawing")
        elif options.export_area_type == "custom":
            command.append("--export-area={}".format(options.export_area_size))
        else:
            command.append("--export-area-page")

        # Export res - default: no arguments
        if options.export_res_type == "dpi":
            command.append("--export-dpi={}".format(options.export_res_dpi))
        elif options.export_res_type == "size":
            command.append("--export-width={}".format(options.export_res_width))
            command.append("--export-height={}".format(options.export_res_height))

        return command

    def construct_thread(self, doc, base_command, use_logging):
        def export_layer_threaded(layer_infos):
            export_doc = copy.deepcopy(doc)
            command = copy.deepcopy(base_command)

            # Add the layer inside fresh document
            layer = layer_infos[0]
            root = export_doc.getroot()
            layer.attrib["style"] = "display:inline"
            root.append(layer)

            label_attrib_name = "{%s}label" % layer.nsmap["inkscape"]
            label = layer[label_attrib_name]

            path = layer_infos[1]

            # Save the data in a temporary file
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".svg"
            ) as temporary_file:

                logging.debug("    Creating temp file {}".format(temporary_file.name))
                export_doc.write(temporary_file.name)
                temporary_file.close()

                logging.debug("  Exporting [{}] as {}".format(label, path))
                self.export_to_file(
                    command.copy(),
                    temporary_file.name,
                    path,
                    use_logging,
                )

            os.remove(temporary_file.name)
            return True

        return export_layer_threaded

    """
    # Delete/Hide unwanted layers to create a clean svg file that will be exported
    def manage_layers(self, target_layer_id, show_layer_ids, hide_layers):
        # Create a copy of the current document
        doc = copy.deepcopy(self.working_doc)
        target_layer_found = False
        target_layer = None

        # Iterate through all layers in the document
        for layer in doc.xpath(
            '//svg:g[@inkscape:groupmode="layer"]', namespaces=inkex.NSS
        ):
            layer_id = layer.attrib["id"]
            layer_label = layer.attrib["{%s}label" % layer.nsmap["inkscape"]]

            # Store the target layer
            if not target_layer_found and layer_id == target_layer_id:
                target_layer = layer
                target_layer_found = True

            # Hide/Delete unwanted layers - hide for use_with_clones = TRUE
            if layer_id not in show_layer_ids:
                if hide_layers:
                    layer.attrib["style"] = "display:none"
                    logging.debug("    Hiding: [{}, {}]".format(layer_id, layer_label))
                else:
                    layer.getparent().remove(layer)
                    logging.debug(
                        "    Deleting: [{}, {}]".format(layer_id, layer_label)
                    )

        # Add the target layer as the single layer in the document
        # This option is used, only when all the layers are deleted above
        # TODO verify it
        root = doc.getroot()
        if target_layer == None:
            logging.debug(
                "    Error: Target layer not found [{}]".format(show_layer_ids[0])
            )
        target_layer.attrib["style"] = "display:inline"
        root.append(target_layer)

        # Save the data in a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temporary_file:
            logging.debug("    Creating temp file {}".format(temporary_file.name))
            doc.write(temporary_file.name)
            return temporary_file.name
    """

    def get_advanced_name(self, template_name, counter, layer_label):
        file_name = template_name
        # TODO hierarchy
        file_name = file_name.replace("[LAYER_NAME]", layer_label)
        file_name = file_name.replace("[NUM]", str(counter))
        file_name = file_name.replace("[NUM-1]", str(counter).zfill(1))
        file_name = file_name.replace("[NUM-2]", str(counter).zfill(2))
        file_name = file_name.replace("[NUM-3]", str(counter).zfill(3))
        file_name = file_name.replace("[NUM-4]", str(counter).zfill(4))
        file_name = file_name.replace("[NUM-5]", str(counter).zfill(5))
        return file_name

    def export_to_file(self, command, svg_path, output_path, use_logging):
        command.append("--export-filename=%s" % output_path)
        command.append(svg_path)
        logging.debug("{}\n".format(command))

        # TODO Create folders path

        try:
            if use_logging:
                # If not piped, stdout and stderr will be showed in an inkscape dialog at the end.
                # Inkscape export will create A LOT of warnings, most of them repeated, and I believe
                # it is pointless to crowd the log file with these warnings.
                with subprocess.Popen(command) as proc:
                    proc.wait(timeout=300)
            else:
                with subprocess.Popen(
                    command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                ) as proc:
                    proc.wait(timeout=300)
        except OSError:
            logging.debug("Error while exporting file {}.".format(command))
            inkex.errormsg("Error while exporting file {}.".format(command))
            exit()


def _main():
    exporter = BatchExporter()
    exporter.run()
    exit()


if __name__ == "__main__":
    _main()
